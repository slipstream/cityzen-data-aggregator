#!/usr/bin/env python

import re
import sys
import json
import time
import socket
import numbers
import logging
import requests

from datetime import date, datetime, timedelta

import requests.packages.urllib3
requests.packages.urllib3.disable_warnings()

from requests.auth import HTTPBasicAuth
from requests.structures import CaseInsensitiveDict

import conf


def is_number(x, boolean=True):
    '''
    Check if x is a number (int, float, ...).
    If 'boolean' is set to True boolean will be considered as number
    '''
    if not boolean and isinstance(x, bool):
        return False
    return isinstance(x, numbers.Number)


class EcoWasteAPI(requests.Session):

    def __init__(self, endpoint, username, password, client_identifier, verify_cert=True):
        super(EcoWasteAPI, self).__init__()

        self.endpoint = endpoint
        self.username = username
        self.password = password
        self.client_identifier = client_identifier

        self.token_expiry_date = None

        self.verify = verify_cert
        self.headers = {'Accept': 'application/json'}

        self.__token = None

    def request(self, *args, **kwargs):
        super_request = super(EcoWasteAPI, self).request

        method = args[0] if len(args) >= 1 else kwargs.get('method', 'get')

        kwargs['headers'] = CaseInsensitiveDict(kwargs.get('headers', {}))
        kwargs['headers']['X-Client-Token'] = self.token
        if 'Content-Type' not in kwargs['headers'] and method.lower() in ['post', 'put', 'patch']:
            kwargs['headers']['Content-Type'] = 'application/json'

        response = super_request(*args, **kwargs)
        if response.status_code == 401:
            self.authenticate()
            response = super_request(*args, **kwargs)

        return response

    @property
    def token(self):
        if self.__token is None or self.is_token_expired():
            self.authenticate()
        return self.__token

    @token.setter
    def token(self, value):
        self.__token = value

    def is_token_expired(self):
        return self.token_expiry_date is None \
               or self.token_expiry_date <= datetime.utcnow()

    def authenticate(self):
        uri = '/ipServer/wise/public/api/authentification/requestToken'

        headers = {'Accept': 'application/json',
                   'Content-Type': 'application/json'}

        auth = auth=HTTPBasicAuth(self.username, self.password)

        data = {'applicationName': 'WISE',
                'clientIdentifier': self.client_identifier}

        response = requests.post('{}{}'.format(self.endpoint, uri), headers=headers,
                                 auth=auth, data=json.dumps(data), verify=self.verify)
        response.raise_for_status()

        response_json = response.json()

        self.token = response_json.get('access_token')

        expires_in = response_json.get('expires_in')
        if expires_in:
            self.token_expiry_date = datetime.now() + timedelta(seconds=expires_in)


class EcoWaste(object):

    def __init__(self, name, endpoint, username, password, client_identifier,
                 country, city, weight_flows, verify_cert=True):
        self.name = name
        self.endpoint = endpoint
        self.country = country
        self.city = city
        self.weight_flows = weight_flows
        self.api = EcoWasteAPI(endpoint, username, password, client_identifier, verify_cert)

    def _get_data(self, resource, *args, **kwargs):
        response = self.api.get(self.endpoint + '/ipServer/wise/api/dashboards/' + resource, *args, **kwargs)
        data = response.json()
        if response.status_code != 200:
            try:
                reason = data.get('reason') or response.text
                print 'HTTP error. HTTP Status Code: {}. Reason: {}'.format(response.status_code,
                                                                            reason)
            except:
                pass
            response.raise_for_status()
            return None
        return data

    def get_weight(self, flow_type_id, start_date=None, end_date=None):
        if start_date is None:
            start_date = date.today().strftime('%Y-%m')
        if end_date is None:
            end_date = start_date
        return self._get_data('weight', params={'flowTypeId': flow_type_id,
                                                'startDate': start_date,
                                                'endDate': end_date})

    def get_equipement(self):
        return self._get_data('equipment')

    def get_communication(self):
        return self._get_data('communication')

    def get_level(self):
        return self._get_data('level')

    def _extract_metrics(self, prefix, data):
        metrics = {'{}.{}'.format(prefix, name): value for name, value in data.items() if is_number(value)}
        return metrics

    def get_metrics(self):
        metrics = {}
        metrics_prefix = '{}.{}.{}'.format(self.name, self.country, self.city)

        for name, flow_type_id in self.weight_flows.items():
            metrics.update(self._extract_metrics(metrics_prefix + '.weight-' + name, self.get_weight(flow_type_id)[0]))

        metrics.update(self._extract_metrics(metrics_prefix + '.equipment', self.get_equipement()))
        metrics.update(self._extract_metrics(metrics_prefix + '.communication', self.get_communication()))
        metrics.update(self._extract_metrics(metrics_prefix + '.level', self.get_level()))

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
    api = EcoWaste(conf.name, conf.endpoint, conf.username, conf.password, conf.client_identifier,
                   conf.country, conf.city, conf.weight_flows, conf.verify_cert)

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

