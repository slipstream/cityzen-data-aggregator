#!/usr/bin/env python

import re
import sys
import time
import socket
import logging
import requests

import requests.packages.urllib3
requests.packages.urllib3.disable_warnings()
import .conf

class Owlet(object):
    
    def __init__(self, name, endpoint, username, password, client_cert,
                 app_names, metrics, cities, districts, streets, devices):
        self.name = name
        self.endpoint = endpoint
        self.username = username
        self.password = password
        self.client_cert = client_cert
        self.__app_names = app_names
        self.__metrics = metrics
        self.__cities = cities
        self.__districts = districts
        self.__streets = streets
        self.devices = devices
    
    def _get_data(self, device):
        response = requests.get('%s/%s' % (self.endpoint, device), 
                                params={'UN': self.username, 'PW': self.password},
                                verify=self.verify_cert,
                                cert=self.client_cert)
        if response.status_code != 200:
            print 'HTTP error. HTTP Status Code: %s' % response.status_code
            response.raise_for_status()
            return None
        return response.json()

    def get_metrics(self):
        #print 'get_metrics called'
        metrics = {}
        
        for device in self.devices:
            try:
                time = None
                data = self._get_data(device)
                if not data:
                    print 'No data for %s. Ignoring it.' % device
                    continue

                country, city, district_street, device_shortname = device.split('_', 3)
                district = district_street[:3]
                street = district_street[3:]

                name = '.'.join([country, 
                                 self.__cities.get(city, city), 
                                 self.__districts.get(district, district), 
                                 self.__streets.get(street, street), 
                                 device_shortname])

                for app_id, raw_metrics in data[data.keys()[0]].items():
                    if app_id not in self.__app_names:
                        #print 'App %s is unknown. Ignore it.' % app_id
                        continue
                    
                    for metric_id, value in raw_metrics.items():
                        if metric_id not in self.__metrics:
                            #print 'Metric %s is unknown. Ignore it.' % (metric_id)
                            continue
                        
                        metric = self.__metrics.get(metric_id)
                        if not metric or 'name' not in metric:
                            print '__metrics not defined correctly. Ignore it.' % (metric_id)
                            continue
                        
                        metric_name = '%s-%s' % (self.__app_names.get(app_id),
                                                 metric.get('name'))
                        
                        metrics[name + '.' + metric_name] = value                  
            except Exception as e:
                print 'Error to process data for "%s": %s' % (device, e)
        
        return metrics


def send_metrics(metrics):
    if metrics is None:
        print 'No metric to send'
        return
    
    metrics_data = ''
    for name, value in metrics.items():
        print name, '=', value
        metrics_data += '%s %s %s\n' % (name, value, int(time.time()))
    
    if metrics_data:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(5)
        s.connect((conf.graphite_address, conf.graphite_port))
        s.sendall(metrics_data)
        s.close()


def catch_exception(message, runnable, *args, **kwargs):
    try:
        return runnable(*args, **kwargs)
    except KeyboardInterrupt:
        raise
    except Exception as e:
        print message % e


def main():
    api = Owlet(conf.name, conf.endpoint, conf.username, conf.password, conf.client_cert,
                conf.app_names, conf.metrics, conf.cities, conf.districts, conf.streets, conf.devices)
    
    while True:
        t = time.time()
        metrics = catch_exception('Failed to get metrics: %s', api.get_metrics)
        catch_exception('Failed to send metrics: %s', send_metrics, metrics)
        
        sleep = 60 - (time.time() - t)
        if sleep > 0:
            time.sleep(sleep)


if __name__ == "__main__":
    logging.getLogger().setLevel(logging.INFO)
    exit(main())

