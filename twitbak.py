#!/usr/bin/env python
import json
import optparse
import os
import sys
import urllib2
from dateutil.parser import parse


class Config():
    """
    Wrapper object around options passed via cli
    """
    
    # Default config values
    auto_mode = False
    include_replies = False
    last_tweet_id = None
    output_path = 'tweets.txt'
    page = 1
    
    def __init__(self, options):
        if options.page:
            self.page = options.page
        
        if options.include_replies:
            self.include_replies = True
        
        if options.last_tweet_id:
            self.last_tweet_id = options.last_tweet_id
            
        if options.output_path:
            self.output_path = options.output_path
        
        if options.auto_mode:
            self.init_auto_mode()
    
    def init_auto_mode(self):
        self.auto_mode = True
        try:
            self.last_tweet_id = self.find_last_tweet_id()
        except:
            raise Exception('Unable to determine last tweet ID, try running script in non-auto mode first')
    
    def find_last_tweet_id(self):
        # Tries to determine the most recent tweet ID from the output file
        if os.path.exists(self.output_path):
            f = open(self.output_path, 'r')
            tweet_id = f.readline().split('\t')[2].rstrip() # Hey, this line makes me feel like a pro
            f.close()
            if tweet_id: return tweet_id
        raise Exception
        

class Fetcher():
    """
    Class to execute requests to Twitter's API and fetch tweets 
    """
    # Twitter's API base URL to retrieve timeline
    BASE_URL = 'https://api.twitter.com/1/statuses/user_timeline.json?screen_name=%s&include_rts=true&exclude_replies=%s'

    # Default options
    exclude_replies = 'true'
    since_id = None
        
    def __init__(self, username, config):
        self.username = username
        if config.include_replies:
            self.exclude_replies = 'false'
        
        if config.last_tweet_id:
            self.since_id = config.last_tweet_id
            
    def get_url(self, page):
        url = self.BASE_URL % (self.username, self.exclude_replies)
        if self.since_id is not None:
            url = '%s&since_id=%s' % (url, self.since_id)
        return "%s&page=%s" % (url, page)
        
    def fetch(self, page=1):
        url = self.get_url(page)
        req = urllib2.Request(url)
        res = urllib2.urlopen(req)
        raw_response = res.read()
        res.close()
        return raw_response
        

class Storage():
    """
    Manages tweets storage
    """
    config = None
    is_dirty = False
    
    def __init__(self, config):
        self.config = config
        
        self.final_path = self.config.output_path
        self.tmp_path = '%s.tmp' % self.final_path
        
        # When working in auto_mode write tweets into temporary file
        # which then will get merged into final output file
        if self.config.auto_mode:
            self.writable_path = self.tmp_path
        else:
            self.writable_path = self.final_path
            
    def store_tweet(self, tweet):
        cols = [tweet.text, tweet.created_date, str(tweet.id)]
        line = "%s\n" % "\t".join(cols)
        line = line.encode('UTF-8')
        self.write(line)
        
    def write(self, content):
        f = open(self.writable_path, 'a')
        f.write(content)
        f.close()
        self.is_dirty = True
    
    def merge(self):
        if self.config.auto_mode is False or self.is_dirty is False:
            # Don't take any action when unnecessary
            return
        
        # Merge temp and final paths together to keep the latest tweets on top
        if os.path.exists(self.final_path):
            f = open(self.final_path, 'r')
            self.write(f.read())
            f.close()
            os.remove(self.final_path)
        os.rename(self.tmp_path, self.final_path)
        
    def emergency_cleanup(self):
        if self.writable_path == self.tmp_path and os.path.exists(self.writable_path):
            os.remove(self.writable_path)
        
    
class Parser():
    """
    Receives raw response from API and converts it into something useful,
    ie. collection of Tweet objects
    """
    def parse_response(self, raw_response):
        json_collection = json.loads(raw_response)
        if len(json_collection) == 0:
            # TODO: raise exception instead?
            return None
        
        tweets_collection = []
        for item in json_collection:
            tweets_collection.append(Tweet(item))
        
        return tweets_collection

class Tweet():
    """
    A tweet class which wraps around raw json tweet data retrieved from API
    """
    def __init__(self, raw_tweet):
        self.data = raw_tweet
        
    @property
    def id(self):
        return self.data['id']
    
    @property
    def text(self):
        return self.data['text']
    
    @property
    def created_date(self):
        return parse(self.data['created_at']).strftime('%Y-%m-%d %H:%M:%S')
    
    
def spin(config, fetcher, storage):
    """
    This is when action happens
    """
    page = 1
    if config.auto_mode is True:
        sys.stdout.write('Running in AUTO mode, found last tweet ID %s\n' % config.last_tweet_id)
    
    if config.page != page:
        page = int(config.page)
        sys.stdout.write('Start retrieving tweets from page %d\n' % page)
        
    total_count = 0
    retry_limit = 3
    prev_ids_buffer = []
    while (True):
        try:
            sys.stdout.write('Fetching page %d ' % page)
            tweets = Parser().parse_response(fetcher.fetch(page))
        except urllib2.HTTPError as e:
            sys.stderr.write("Oops: %s\n" % str(e))
            sys.stderr.write("Hint: hourly limit has been exhausted, perhaps?")
            retry_limit = retry_limit - 1
            if retry_limit == 0:
                sys.stderr.write("Giving up...\n")
                break
            sys.stderr.write("Retrying...\n")
            continue
        
        if tweets is None or len(tweets) == 0: 
            sys.stdout.write("- no tweets have been retrieved from request, quitting\n")
            break
        
        sys.stdout.write('- retrieved %d tweets ' % len(tweets))
        # IDs buffer is used to prevent tweets overlaping between requests,
        # which seem to happen when requests are ignoring reply tweets
        current_ids_buffer = []
        current_count = 0
        for tweet in tweets:
            current_ids_buffer.append(tweet.id)
            if tweet.id not in prev_ids_buffer:
                storage.store_tweet(tweet)
                current_count = current_count + 1
                total_count = total_count + 1
            
        page = page + 1
        prev_ids_buffer = current_ids_buffer
        sys.stdout.write('- processed %d tweets (%d total)\n' % (current_count, total_count))
        
    # Don't forget to merge output files once job is done! 
    # (only applies in auto mode, tough)
    storage.merge()


if __name__ == "__main__":
    parser = optparse.OptionParser("Usage: %prog [options] twitter_username\n\nRetrieves given username's Twitter timeline into tweets.txt file,\nexcluding any reply tweets by default.")
    parser.add_option('-a', '--auto', 
                      action="store_true", 
                      dest="auto_mode", 
                      help='Automatically determine the most recent tweet ID and only retrieve tweets newer than that. Note: retrieved tweets in automatic mode are stored at the beginning of the output file to maintain default reverse chronological order')
    parser.add_option('-i', '--last-tweet-id', 
                      action="store", 
                      dest="last_tweet_id", 
                      help='Manually specify tweet ID to only retrieve tweets newer than that')
    parser.add_option('-p', '--page', 
                      action="store", 
                      dest="page", 
                      help='Page number to start retrieving tweets from Twitter\'s API. Useful to resume fetching after exhausting hourly limit. Starts from page 1 by default')
    parser.add_option('-r', '--include-replies', 
                      action="store_true", 
                      dest="include_replies", 
                      help='Should replies (tweets starting with @) be retrieved')
    parser.add_option('-o', '--output-path', 
                      action="store", 
                      dest="output_path", 
                      help='Path to the file where tweets should be saved - local tweets.txt file by default')
    
    (opts, args) = parser.parse_args()
    
    try:
        username = args[0]
        config = Config(opts)
        storage = Storage(config)
        fetcher = Fetcher(username, config)
        spin(config, fetcher, storage)
        sys.stdout.write('\nGood bye\n')
    except IndexError:
        # Username argument is required
        sys.stderr.write('No twitter username specified\n')
    except Exception as e:
        # Generic exception
        sys.stderr.write(str(e) + '\n')
    except KeyboardInterrupt:
        # CTRL-C addicts
        sys.stdout.write('\nReally sad to see you go...\n')
        storage.emergency_cleanup()
