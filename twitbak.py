#!/usr/bin/python

import urllib2
import json
import sys
from dateutil.parser import parse

def fetch(page=1):
    url = 'https://api.twitter.com/1/statuses/user_timeline.json?include_rts=true&exclude_replies=true&screen_name=adlorenz&page=%d' % page
    req = urllib2.Request(url)
    res = urllib2.urlopen(req)
    tweets = json.loads(res.read())
    res.close()
    return tweets

def store(line):
    f = open('twitbak.txt', 'a')
    f.write(line)
    f.close()

def spin():
    try:
        page = 127
        total = 0
        prev_ids_buffer = []
        while (True):
            try:
                sys.stdout.write('Fetching page %d ' % page)
                tweets = fetch(page)
            except urllib2.HTTPError as e:
                sys.stderr.write("Oops: %s\n" % str(e))
                sys.stderr.write("Retrying...\n")
                continue
            if len(tweets) == 0: break
            sys.stdout.write('- fetched %d tweets ' % len(tweets))
            current_ids_buffer = []
            count = 0
            for tweet in tweets:
                tweet_id = str(tweet['id'])
                tweet_date = parse(tweet['created_at']).strftime('%Y-%m-%d %H:%M:%S')
                current_ids_buffer.append(tweet_id)
                if tweet_id not in prev_ids_buffer:
                    cols = [tweet['text'], tweet_date, tweet_id]
                    line = "%s\n" % "\t".join(cols)
                    line = line.encode('UTF-8')
                    #sys.stdout.write(line)
                    store(line)
                    count = count + 1
                    total = total + 1
                
            page = page + 1
            prev_ids_buffer = current_ids_buffer
            sys.stdout.write('- processed %d tweets (%d total)\n' % (count, total))
            
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    spin()