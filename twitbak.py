#!/usr/bin/python
import json
import optparse
import os
import sys
import urllib2
from dateutil.parser import parse


class Config():
    """
    Configuration object which handles options passed via cli and also
    reads/writes persistent configuration
    """
    LAST_TWEET_ID_FILENAME = '.twitbak.last_tweet_id'
    
    # Default config values
    auto_mode = False
    include_replies = False
    last_tweet_id = None
    output_path = 'tweets.txt'
    page = 1
    
    def __init__(self, options):
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
        self.last_tweet_id_filepath = '%s/%s' % (os.environ.get('HOME'), self.LAST_TWEET_ID_FILENAME)
        if os.path.exists(self.last_tweet_id_filepath):
            f = open(self.last_tweet_id_filepath, 'r')
            # TODO: raise exception when last_tweet_id is not found or empty
            last_tweet_id = f.read()
            self.last_tweet_id = last_tweet_id.rstrip()
            f.close()
    
    def save_last_tweet_id(self, tweet_id):
        # TODO: race condition - self.last_tweet_id_filepath must be set beforehand
        f = open(self.last_tweet_id_filepath, 'w')
        f.write(tweet_id)
        f.close()
        

class Fetcher():
    """
    Class to execute requests to Twitter's API and fetch tweets 
    """
    
    BASE_URL = 'https://api.twitter.com/1/statuses/user_timeline.json?screen_name=%s&include_rts=true&exclude_replies=%s'
    
    exclude_replies = 'true'
    since_id = None
        
    def __init__(self, username, config):
        self.username = username
        if config.include_replies:
            self.exclude_replies = 'false'
        
        if config.last_tweet_id:
            self.since_id = config.last_tweet_id
            
    def set_last_tweet_id(self, tweet_id):
        self.since_id = tweet_id
            
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
    
    def __init__(self, config):
        self.config = config
        
        self.final_path = self.config.output_path
        self.tmp_path = '%s.tmp' % self.final_path
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
        
    def merge(self):
        if self.config.auto_mode is False:
            return
        
        if os.path.exists(self.final_path):
            f = open(self.final_path, 'r')
            self.write(f.read())
            f.close()
            os.remove(self.final_path)
        os.rename(self.tmp_path, self.final_path)
        
    
class Parser():
    """
    Receives raw response from API and converts it into something useful
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
    A class representing a simple tweet
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
    page = 1
    if config.auto_mode is True:
        sys.stdout.write('Running in AUTO mode, found last tweet ID %d' % config.last_tweet_id)
    
    if config.auto_mode is False and config.page != page:
        page = int(config.page)
        sys.stdout.write('Starting retrieving tweets from page %d' % page)
        
    total_count = 0
    retry_limit = 3
    prev_ids_buffer = []
    while (True):
        try:
            sys.stdout.write('Fetching page %d ' % page)
            tweets = Parser().parse_response(fetcher.fetch(page))
        except urllib2.HTTPError as e:
            sys.stderr.write("Oops: %s\n" % str(e))
            retry_limit = retry_limit - 1
            if retry_limit == 0:
                sys.stderr.write("Giving up...\n")
                break
            sys.stderr.write("Retrying...\n")
            continue
        
        if tweets is None or len(tweets) == 0: 
            sys.stdout.write("- no more tweets have been retrieved, quitting\n")
            break
        
        sys.stdout.write('- retrieved %d tweets ' % len(tweets))
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


if __name__ == "__main__":
    parser = optparse.OptionParser("Usage: %prog [options] twitter_username")
    parser.add_option('-a', '--auto', 
                      action="store_true", 
                      dest="automode", 
                      help='Automatic mode - pick up last tweet ID from ~/.twitbak file and append new tweets at the beginning of output file')
    parser.add_option('-o', '--output-path', 
                      action="store_tweet", 
                      dest="final_path", 
                      help='Path to the file where tweets should be saved')
    parser.add_option('-i', '--last-tweet-id', 
                      action="store_tweet", 
                      dest="last_tweet_id", 
                      help='Manually specify tweet ID to only retrieve tweets newer than this')
    parser.add_option('-p', '--page', 
                      action="store_tweet", 
                      dest="page", 
                      help='Page number to start retrieving tweets from in Twitter\'s API (starts from page 1 by default). Useful to resume fetching after reaching hourly limit')
    parser.add_option('-r', '--include-replies', 
                      action="store_true", 
                      dest="include_replies", 
                      help='Should replies (tweets starting with @) be retrieved')
#    parser.add_option('-q', '--quiet', 
#                      action="store_true", 
#                      dest="quiet", 
#                      help='Do not produce any output')
    
    (opts, args) = parser.parse_args()
    
    try:
        username = args[0]
        config = Config(opts)
        storage = Storage(config)
        fetcher = Fetcher(username, config)
        spin(config, fetcher, storage)
        storage.merge()
    except IndexError:
        sys.stderr.write('No twitter username specified\n')
    except KeyboardInterrupt:
        storage.merge()
