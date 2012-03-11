#!/usr/bin/python
import json
import optparse
import sys
import urllib2
from dateutil.parser import parse

class Fetcher():
    """
    Class to execute requests to Twitter's API and fetch tweets 
    """
    
    BASE_URL = 'https://api.twitter.com/1/statuses/user_timeline.json?screen_name=%s&include_rts=true&exclude_replies=%s'
    
    def __init__(self, username, options):
        self.username = username
        self.exclude_replies = 'true'
        self.since_id = None
        
        if options.include_replies:
            self.exclude_replies = 'false'
        
        if options.last_tweet_id:
            self.since_id = options.last_tweet_id
            
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
    def __init__(self, output_path=None):
        self.output_path = output_path or 'twitbak.txt'

    def store(self, tweet):
        cols = [tweet.text, tweet.created_date, str(tweet.id)]
        line = "%s\n" % "\t".join(cols)
        line = line.encode('UTF-8')
        self.write(line)
        
    def write(self, line):
        file = open(self.output_path, 'a')
        file.write(line)
        file.close()
    
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
    
def spin(username, options):
    page = 1
    if options.page is not None:
        page = int(options.page)
    total_count = 0
    prev_ids_buffer = []
    fetcher = Fetcher(username, options)
    storage = Storage(options.output_path)
    while (True):
        try:
            sys.stdout.write('Fetching page %d ' % page)
            tweets = Parser().parse_response(fetcher.fetch(page))
        except urllib2.HTTPError as e:
            sys.stderr.write("Oops: %s\n" % str(e))
            sys.stderr.write("Retrying...\n")
            continue
        
        if tweets is None or len(tweets) == 0: 
            sys.stdout.write("- no tweets have been retrieved, quitting\n")
            break
        
        sys.stdout.write('- retrieved %d tweets ' % len(tweets))
        current_ids_buffer = []
        current_count = 0
        for tweet in tweets:
            current_ids_buffer.append(tweet.id)
            if tweet.id not in prev_ids_buffer:
                storage.store(tweet)
                current_count = current_count + 1
                total_count = total_count + 1
            
        page = page + 1
        prev_ids_buffer = current_ids_buffer
        sys.stdout.write('- processed %d tweets (%d total)\n' % (current_count, total_count))

if __name__ == "__main__":
    parser = optparse.OptionParser("Usage: %prog [options] twitter_username")
    parser.add_option('-o', '--output-path', 
                      action="store", 
                      dest="output_path", 
                      help='Path to the file where tweets should be saved')
    parser.add_option('-p', '--page', 
                      action="store", 
                      dest="page", 
                      help='Page number to start retrieving tweets from (by default start from page 1)')
    parser.add_option('-i', '--last-tweet-id', 
                      action="store", 
                      dest="last_tweet_id", 
                      help='Only retrieve tweets newer than tweet with given ID')
    parser.add_option('-r', '--include-replies', 
                      action="store_true", 
                      dest="include_replies", 
                      help='Should replies (tweets starting with @) be retrieved')
    parser.add_option('-q', '--quiet', 
                      action="store_true", 
                      dest="quiet", 
                      help='Do not produce any output')
    
    (opts, args) = parser.parse_args()
    
    try:
        username = args[0]
        spin(username, opts)
    except IndexError:
        sys.stderr.write('No twitter username specified\n')
    except KeyboardInterrupt:
        pass
