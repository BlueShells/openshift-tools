#!/usr/bin/env python2
# vim: expandtab:tabstop=4:shiftwidth=4

#   Copyright 2015 Red Hat Inc.
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

'''
    Metric Manager - manages a persistent list of zabbix metrics

    Example Usage:
        # Create a metric and write it to disk:
        zbx_metric = UniqueMetric('a.example.com','a.b.c','10')
        hb_metric = UniqueMetric.create_heartbeat('a.example.com', ['host template'], ['default'])

        mm = MetricManager('/tmp/metrics')
        mm.write_metrics([zbx_metric, hb_metric]) # this can be a single metric too!

        # Read metrics from disk and print them:
        all_metrics = mm.read_metrics()

        # Print out just the zabbix metrics:
        for metric in mm.filter_zbx_metrics(all_metrics):
            print metric

        # Print out just the heartbeat metrics:
        for metric in mm.filter_heartbeat_metrics(all_metrics):
            print metric

        # Delete this specific metric from disk
        mm.remove_metrics([zbx_metric, hb_metric]) # this can be a single metric too!
'''

import yaml
import os
import uuid
import calendar
import time
import zbxsend


# Reason: disable pylint too-few-public-methods because this is
#     a DTO with a little ctor logic.
# Status: permanently disabled
# pylint: disable=too-few-public-methods
class UniqueMetric(zbxsend.Metric):
    ''' Represents a unique metric being reported on. Inherits from Metric and
        adds a unique ID, plus also adds auto-populating of the clock value.
    '''

    # Reason: disable pylint too-many-arguments because this is a data only
    #         object, and we like to use the constructor to populate the
    #         data easily.
    # Status: permanently disabled.
    # pylint: disable=too-many-arguments
    def __init__(self, host, key, value, clock=None, unique_id=None):
        ''' Construct object

            Keyword arguments:
            host      -- the host that the metric is for
            key       -- the zabbix item name
            value     -- the value that zabbix should put in for the key
            clock     -- the time the metric was taken (default: current time)
            unique_id -- the unique id of this metric (default: generate one)
        '''

        if clock == None:
            clock = calendar.timegm(time.gmtime())

        if unique_id == None:
            self.unique_id = str(uuid.uuid4()).replace('-', '')
        else:
            self.unique_id = unique_id

        self.filename = self.unique_id + '.yml'

        super(UniqueMetric, self).__init__(host, key, value, clock)

    @staticmethod
    def create_heartbeat(host, templates, hostgroups, clock=None, unique_id=None):
        ''' Construct a heartbeat specific metric

              Keyword arguments:
              host       -- the host that the metric is for
              templates  -- the list of zabbix templates this host belongs to
              hostgroups -- the list of zabbix hostgroups this host belongs to
              clock      -- the time the metric was taken (default: current time)
              unique_id  -- the unique id of this metric (default: generate one)
        '''

        if isinstance(templates, basestring):
            templates = templates.split(",")

        if isinstance(hostgroups, basestring):
            hostgroups = hostgroups.split(",")

        return UniqueMetric(
            host=host,
            key='heartbeat',
            value={
                'hostgroups': hostgroups,
                'templates': templates,
            },
            clock=clock,
            unique_id=unique_id
        )

    @staticmethod
    def from_request(data):
        """
        Method to receive UniqueMetric data from a request dict

        """
        result = []
        if isinstance(data, dict):
            data = [data]
        for metric in data:
            result.append(UniqueMetric(host=metric['host'],
                                       key=metric['key'],
                                       value=metric['value'],
                                       clock=metric['clock']
                                      )
                         )
        return result

    def to_dict(self):
        """
        return object as a dict
        """
        return {'host': self.host,
                'key': self.key,
                'value': self.value,
                'clock': self.clock,
                'unique_id': self.unique_id,
               }

    def __repr__(self):
        ''' How this object is represented as a string '''
        return 'UniqueMetric(%r, %r, %r, %r, %r)' % (self.host, self.key, self.value, self.clock, self.unique_id)

class MetricManager(object):
    ''' Manages a disk cache of metrics.
    '''

    def __init__(self, metrics_directory):
        ''' Construct object

            Keyword arguments:
            metrics_directory -- the directory where the metrics should be stored
        '''
        self.metrics_directory = metrics_directory

    def metric_full_path(self, filename):
        ''' generates the full path of a specific metric.

            Keyword arguments:
            filename -- the filename of the metric.
        '''
        return os.path.join(self.metrics_directory, filename)

    def write_metrics(self, metrics):
        ''' write one or more metrics to disk

            Keyword arguments:
            metrics -- a single metric, or a list of metrics to be written to disk
        '''
        if not isinstance(metrics, list):
            metrics = [metrics]

        for metric in metrics:
            with open(self.metric_full_path(metric.filename), 'w') as metric_file:
                yaml.safe_dump(metric.__dict__, metric_file, default_flow_style=False)

    def remove_metrics(self, metrics):
        ''' remove one or more metrics from disk

            Keyword arguments:
            metrics -- a single metric, or a list of metrics to be removed from disk
        '''
        if not isinstance(metrics, list):
            metrics = [metrics]

        for metric in metrics:
            os.unlink(self.metric_full_path(metric.filename))

    def read_metrics(self):
        ''' read in all of the metrics contained in the disk cache

            Keyword arguments:
            None
        '''
        metrics = []

        for filename in os.listdir(self.metrics_directory):
            ext = os.path.splitext(filename)[-1][1:].lower().strip()

            # We only want to load yaml files
            if ext not in ['yml', 'yaml']:
                continue

            with open(self.metric_full_path(filename), 'r') as metric_file:
                doc = yaml.load(metric_file)
                metrics.append(UniqueMetric(doc['host'], doc['key'], doc['value'],
                                            doc['clock'], doc['unique_id']))
        return metrics

    @staticmethod
    def filter_zbx_metrics(metrics):
        ''' return only zabbix related metrics from the list

            Keyword arguments:
            metrics -- a single metric, or a list of metrics
        '''
        return [m for m in metrics if m.key != 'heartbeat']

    @staticmethod
    def filter_heartbeat_metrics(metrics):
        ''' return only heartbeat metrics from the list

            Keyword arguments:
            metrics -- a single metric, or a list of metrics
        '''
        return [m for m in metrics if m.key == 'heartbeat']
