Twitbak
=======

Twitbak allows creating a backup of your Twitter's public timeline into a local 
plain/text file.


Rationale
---------

In case you didn't know, Twitter only allows last 3200 tweets to be recovered from 
any user's timeline using API, so if you've produced, say 3500 tweets in your timeline 
(inluding retweets and replies), the first 300 would be gone somewhere in distant 
Twitterverse forever.

I have accidentaly found about this via `Zach Holman's blog article`_ the other day
and thought writing a simple fetcher script to dump tweets into an offline text file 
would be nice Python excercise for a PHP'er keen to learn more Python.

.. _`Zach Holman's blog article`: http://zachholman.com/2010/09/hey-twitter-give-us-our-tweets/


Usage
-----

Retrieve tweets from *username*'s public timeline (excluding replies) into ``tweets.txt`` 
file in current dir where tweets are stored in **reverse chronological** order::

    $ twitbak.py username
    
Run in *auto-mode* - automatically determine most recent tweet ID and only retrieve
tweets from the timeline which are newer than that. Any tweets retrieved in *auto-mode*
are inserted at the beginning of the output file::

    $ twitbak.py -a username
    
To include replies, ie. tweets starting with @ sign (they are ignored by default
by twitbak)::

    $ twitbak.py -r username
    
To specify different output file::

    $ twitbak.py -o /path/to/file.txt username
    
    
API limitation
--------------

Twitter throttles clients using their API to 150 requests per hour. Since single 
request to user_timeline_ webservice returns maximum of 20 tweets at once, hourly 
limit gets exhausted after retrieving maximum of 3000 (150*20) tweets and further 
requests would need to wait additional hour until limit is reset.

.. _user_timeline: https://dev.twitter.com/docs/api/1/get/statuses/user_timeline

To overcome that limitation and continue retrieving remaining tweets in non-hacky
fashion, you can specify particular page number from which requests should be
resumed::

    $ twitbak.py -p 121 username
    
Above will resume fetching tweets from 121st page of the timeline.


Output file format
------------------

Tweets fetched by twitbak are stored in tab-separated values file, one line per
tweet, which looks like this::

    tweet body[TAB]tweet date[TAB]tweet id
    
The first two columns are no-brainer, while tweet ID is kept for reference and 
to make twitbak work nicely in *auto-mode*.


WTFs
----

*Q: Hey, I've posted 500 tweets in my timeline but tweets.txt file only has 200 lines. WTF?!*

A: This is most likely because twitbak ignores replies by default. It would be like
recording only one side of telephone conversation and make very little sense. You 
can still include replies by using -r option.


Author
------
Hi, my name is `Dawid Lorenz`_, I am a web developer with strong PHP background and 
was recently affected with Python/Django love. I treat twitbak as a way to expand 
my Python experience and create something genuienly useful at the same time.

.. _`Dawid Lorenz`: http://dawid.lorenz.co
 
