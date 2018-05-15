#!/usr/bin/env python
#coding=utf-8

import os
import sys
import time
import copy
import gevent
from gevent.pool import Pool
from gevent import monkey
from gevent.lock import RLock
monkey.patch_all()
from Queue import Queue

import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

UserAgent = 'Mozilla/5.0 (Windows NT 10.0; Win64;) Gecko Firefox/59.0'

class Store:
    def __init__(self):
        self.lock = RLock()
        self.results = []
        self.workers = []
        self.errors = []
        self.wqueue = Queue()

    def saveError(self,host):
        self.lock.acquire()
        self.errors.append(host)
        self.lock.release()
        
    def saveResult(self,host):
        self.lock.acquire()
        self.results.append(host)
        self.lock.release()

    def getErrors(self):
        return self.errors
    
    def resetErrors(self):
        self.errors = []
        
    def getResults(self):
        return self.results

    def setWorker(self,worker):
        self.workers.append(worker)
        self.wqueue.put(len(self.workers)-1)
        
    def getWorker(self):
        wid = self.wqueue.get(block=True)
        return [wid, self.workers[wid]]
    
    def returnWorker(self,worker):
        self.wqueue.put(worker[0])
    
def check(param):
    url,host,store = param[0],param[1],param[2]
    worker = store.getWorker()
    headers = {'User-Agent':UserAgent,'Host':host}
    try:
        start = time.time()
        rr = worker[1].get(url,headers=headers,timeout=5,verify=False,allow_redirects=False)
        elapse = time.time()-start
        if rr.content.find('route')>0:
            print '-N: %s %3dms' % (host,1000*elapse)
        else:
            store.saveResult(host)
            print '+O: %s %3dms' % (host,1000*elapse)
            print rr.content
    except Exception as e:
        print '-EXC: [%s]%s' % (host,str(e))
        store.saveError(host)
    store.returnWorker(worker)
        
def main():
    names = set()
    for ln in open(sys.argv[1]):
        names.add(ln.strip().lower())
    domain = sys.argv[2].lower().strip('.')
    addrs = sys.argv[3].split(':')
    
    url = ''
    if addrs[1]=='80':
        url = 'http://%s/' % (addrs[0])
    elif addrs[1]=='443':
        url = 'https://%s/' % (addrs[0])
    else:
        url = 'http://%s:%s/' % (addrs[0],addrs[1])
    poolsize = 20
    store = Store()
    for i in range(poolsize):
        s = requests.Session()
        store.setWorker(s)
        
    pool = Pool(poolsize)
    for name in sorted(names):
        host = '%s.%s' % (name,domain)
        param = [url,host,store]
        pool.spawn(check, param)
    gevent.wait()
    
    errors = copy.copy(store.getErrors())
    store.resetErrors()
    for host in errors:
        param = [url,host,store]
        pool.spawn(check, param)
    gevent.wait()
    
    fs = open('%s.txt'%(domain),'wb')
    results = store.getResults()
    for r in results:
        fs.write('%s\t\t%s\n'%(addrs[0],r))
    errors = store.getErrors()
    for host in errors:
        fs.write('?:%s\t\t%s\n'%(addrs[0],host))
    fs.close()
    
if __name__=='__main__':
    main()
    
