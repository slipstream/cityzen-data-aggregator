#!/usr/bin/env python

import time
import socket
import numbers
import logging
import requests

from collections import namedtuple
from datetime import date, datetime, timedelta

import requests.packages.urllib3
requests.packages.urllib3.disable_warnings()

from requests.auth import HTTPBasicAuth

import conf


Metric = namedtuple('Metric', ['name', 'value', 'timestamp'])


class Xemtec(object):

    def __init__(self, name, endpoint, username, password, country, city,
                 readers_name=None, readers=None, verify_cert=True):
        self.name = name
        self.endpoint = endpoint
        self.username = username
        self.password = password
        self.country = country
        self.city = city
        self.readers_name = readers_name if readers_name else {}
        self.readers = readers
        self.verify_cert = verify_cert

    def get_reader_name(self, reader):
        return self.readers_name.get(reader, reader)

    def _get_data(self, resource, *args, **kwargs):
        if 'auth' not in kwargs:
            kwargs['auth'] = HTTPBasicAuth(self.username, self.password)

        if 'verify' not in kwargs:
            kwargs['verify'] = self.verify_cert

        response = requests.get(self.endpoint + '/api/' + resource, *args, **kwargs)
        data = response.json()

        if response.status_code != 200:
            try:
                reason = data.get('detail') or response.text
                print 'HTTP error. HTTP Status Code: {}. Reason: {}'.format(response.status_code,
                                                                            reason)
            except:
                pass
            response.raise_for_status()
            return None
        return data

    def get_readers(self):
        return [el.get('serial') for el in self._get_data('readers') if 'serial' in el]

    def get_metrics(self):
        metrics = []
        readers = self.readers if self.readers else self.get_readers()

        for reader in readers:
            data = self._get_data('measurements/{}'.format(reader))
            name = self.get_reader_name(reader)

            for el in data:
                timestamp = el.get('timestamp')
                values = el.get('values')
                for i in range(len(values)):
                    value = values[i]
                    metric_name = '{}.{}.{}.{}_{}'.format(self.name, self.country, self.city, name, i+1)
                    metrics.append(Metric(metric_name, value, timestamp))

        return metrics


def send_metrics(metrics):
    if metrics is None:
        print 'No metric to send'
        return

    metrics_data = ''
    for metric in metrics:
        print metric.name, '=', metric.value
        ts = metric.timestamp
        timestamp = ts if ts is not None else time.time()
        metrics_data += '%s %s %s\n' % (metric.name, metric.value, timestamp)

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
    api = Xemtec(conf.name, conf.endpoint, conf.username, conf.password, conf.country, conf.city,
                 conf.readers_name, conf.readers, conf.verify_cert)

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


