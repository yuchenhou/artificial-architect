#!/usr/bin/env python
from multiprocessing import Pool
from shutil import copyfile
from ast import literal_eval
from os import devnull
from os import rename
from pprint import pprint
from copy import copy
from cProfile import run
from fileinput import input
from itertools import combinations
from functools import reduce
from operator import mul
from random import uniform
from shlex import split
from time import strftime
from datetime import datetime
from subprocess import check_call
from simpleai.search import SearchProblem
from simpleai.search.local import hill_climbing
from simpleai.search.local import hill_climbing_stochastic
from simpleai.search.local import hill_climbing_random_restarts
from simpleai.search.local import beam
from simpleai.search.local import beam_best_first
from simpleai.search.local import simulated_annealing
from sklearn.svm import SVR
from sklearn.svm import SVC
from sklearn.grid_search import GridSearchCV
from sklearn.preprocessing import scale
from sklearn.preprocessing import StandardScaler
from networkx import Graph
from networkx import relabel_nodes
from networkx import nodes
from networkx import get_node_attributes
from networkx import get_edge_attributes
from networkx import neighbors
from networkx import is_connected
from networkx import is_strongly_connected
from networkx import diameter
from networkx import number_of_edges
from networkx import radius
from networkx import degree
from networkx import density
from networkx import draw
from networkx import draw_networkx_edge_labels
from networkx import gnm_random_graph
from networkx import grid_2d_graph
from networkx import connected_watts_strogatz_graph
from networkx import navigable_small_world_graph
from networkx import to_numpy_matrix
from networkx import to_dict_of_dicts
from networkx import to_edgelist
from networkx import shortest_path
from networkx import shortest_path_length
from networkx import average_shortest_path_length
from numpy import loadtxt
from numpy import savetxt
from numpy import delete
from numpy import arange
from numpy import asarray
from numpy import histogram
from numpy import zeros
from numpy import average
from numpy import repeat
from numpy import prod
from numpy import fill_diagonal
from numpy import vstack
from numpy import hstack
from numpy import tile
from numpy import hsplit
from numpy import vsplit
from numpy import logspace
from numpy import linspace
from numpy import squeeze
from numpy.linalg import norm
from numpy.random import rand
from pandas import read_csv
from pandas import DataFrame
from pandas import Series
from pandas import concat
from matplotlib import use
use('Agg')
from matplotlib.pyplot import figure
from matplotlib.pyplot import title
from matplotlib.pyplot import savefig

class Critic(object):
    def evaluate_kernels(self, dataset):
        data = actuator.load_data(dataset, range(performer.SAMPLE_COUNT))
        kernels = ['linear', 'poly', 'rbf', 'sigmoid']
        for kernel in kernels:
            svr = SVR(kernel)
            parameters = {'C':logspace(0, 2, 3).tolist()}
            if kernel == 'poly':
                parameters['degree'] = linspace(1, 4, 4, dtype = 'int').tolist()
            if kernel == 'rbf':
                parameters['gamma'] = logspace(-4, 0, 5).tolist()
            estimator = GridSearchCV(svr, parameters, cv = 10, n_jobs = -1)
            estimator.fit(data[2][:-10], data[1][:-10])
            print 'kernel=', kernel,
            print 'best_params=', estimator.best_params_,
            print 'best_score=', estimator.best_score_
        return

class Performer(object):
    architectures = ['mesh', 'small_world', 'freenet']
    # benchmarks = ['bodytrack', 'canneal', 'dedup', 'fluidanimate', 'freqmine', 'swaption', 'vips']
    benchmarks = ['fft', 'lu', 'radix', 'water', 'canneal', 'dedup', 'fluidanimate', 'vips']
    benchmark = None
    optimization_targets = ['latency', 'power', 'latency_power_product']
    optimization_target = None
    document_directory = 'documents/'
    network_directory = 'booksim2/src/examples/anynet/'
    configuration_template = network_directory + 'anynet_config'
    traffic = {}
    for benchmark in benchmarks:
        hotspot = sum(loadtxt('traffic_' + benchmark + '.tsv'))
        injection_rate = sum(hotspot)
        hotspot /= (injection_rate*.0001)
        traffic[benchmark] = hotspot
    injection_rate = 0.00001
    packet_size = 48
    NODE_WEIGHT = 3
    DIMENSION = 2
    RADIX = 8
    DEGREE_AVERAGE = 5
    DEGREE_MAX = 7
    NODE_COUNT = RADIX ** DIMENSION
    EDGE_COUNT_MIN = NODE_COUNT * DEGREE_AVERAGE / 3
    EDGE_COUNT_MAX = NODE_COUNT * DEGREE_AVERAGE / 2
    INITIAL_DATASET_SIZE = 100
    TARGET_NAMES = ['latency', 'power']
    TARGET_TOKENS = ['Packet latency average = ',  '- Channel Wire Power:      ']
    TARGET_COUNT = len(TARGET_NAMES)
    FEATURE_NAMES = ['edge_count', 'path_length', 'diameter', 'radius', 'degree_norm']
    FEATURE_COUNT = len(FEATURE_NAMES)
    SAMPLE_SIZE = TARGET_COUNT + FEATURE_COUNT
    estimators = []
    scaler = StandardScaler()
    def file_name(self, quantity, benchmark = None):
        if benchmark == None:
            temp_name = quantity
            if quantity in ['latency', 'energy', 'latency_energy_product', 'hop_count_average',
                            'path_length_average', 'link_length_average', 'hop_counts', 'path_lengths',
                            'link_lengths']:
                file_name = self.document_directory + temp_name
            elif quantity in ['accuracy']:
                file_name = temp_name + '.tsv'
        else:
            temp_name = quantity + '_' + benchmark
            if quantity in ['trace', 'links', 'result', 'network_figure']:
                file_name = self.document_directory + temp_name
            elif quantity in ['topology', 'configuration']:
                file_name = self.network_directory + temp_name
            elif quantity in ['design', 'dataset']:
                file_name = temp_name + '.tsv'
            elif quantity in ['simulation']:
                file_name = temp_name + '.log'
            else:
                raise NameError('no file for quantity: ' + quantity)
        return file_name
    def extract_features(self, benchmark, graph):
        raw_features = [number_of_edges(graph),
                        self.weighted_length(performer.traffic[benchmark], graph, 'weight'),
                        diameter(graph), radius(graph), norm(graph.degree().values())**2]
        return raw_features
    def set_radix(self, radix):
        self.RADIX = radix
        self.NODE_COUNT = self.RADIX ** self.DIMENSION
        self.EDGE_COUNT_MIN = self.NODE_COUNT * self.DEGREE_AVERAGE / 3
        self.EDGE_COUNT_MAX = self.NODE_COUNT * self.DEGREE_AVERAGE / 2
    def initialize_benchmark(self, benchmark):
        if (benchmark not in self.benchmarks):
            raise NameError('unknown benchmark: ' + benchmark)
        self.benchmark = benchmark
        print 'performer: initialize_benchmark:', self.benchmark + ';'
        return
    def initialize_optimization_target(self, optimization_target):
        if (optimization_target not in self.optimization_targets):
            raise NameError('unknown optimization_target: ' + optimization_target)
        self.optimization_target = optimization_target
        print 'performer: initialize_optimization_target:', self.optimization_target + ';'
        return
    def update_estimators(self, accuracy):
        data = self.load_data(self.file_name('dataset',self.benchmark), range(performer.SAMPLE_SIZE))
        c_range = accuracy
        gamma_range = accuracy
        parameters = {'C' : logspace(0, c_range, c_range+1).tolist(),
                      'gamma' : logspace(- gamma_range, 0, gamma_range+1).tolist()}
        estimators = []
        svrs = []
        data_instance = [datetime.now(), self.benchmark]
        for i in range(self.TARGET_COUNT):
            svrs.append(SVR('rbf'))
            estimators.append(GridSearchCV(svrs[i], parameters, n_jobs = -1))
            estimators[i].fit(data[self.TARGET_COUNT], data[i])
            data_instance += [estimators[i].best_params_, estimators[i].best_score_]
        print  'performer: update_estimator: benchmark =', performer.benchmark+';', data_instance
        with open(self.file_name('accuracy'), 'a') as f:
            f.write('\t'.join(map(str, data_instance)) + '\n')
        self.estimators = estimators
        return
    def edge_weight(self, graph, source, destination):
        manhattan_distance = 0
        for i in range(self.DIMENSION):
            manhattan_distance += abs(graph.node[source]['position'][i] - graph.node[destination]['position'][i])
        weight = manhattan_distance + self.NODE_WEIGHT
        return weight
    def link_length(self, edge_weight):
        length = edge_weight - self.NODE_WEIGHT
        return length
    def center(self, graph, source, destination):
        center = [source, destination]
        for i in range(self.DIMENSION):
            center[i] = .5*(graph.node[source]['position'][i] + graph.node[destination]['position'][i])
        return center
    def constraints_satisfied(self, graph):
        degrees = graph.degree().values()
        degree_average = average(degrees)
        degree_max = max(degrees)
        if degree_average <= self.DEGREE_AVERAGE and degree_max <= self.DEGREE_MAX and is_strongly_connected(graph):
            return True
        else:
            return False
    def process_graph(self, graph):
        graph.remove_edges_from(graph.selfloop_edges())
        for node_key, node_attributes in graph.nodes(data=True):
            node_attributes['position'] = (node_key / self.RADIX, node_key % self.RADIX)
            node_attributes['weight'] = self.NODE_WEIGHT
        for source, destination, edge_attributes in graph.edges(data=True):
            edge_attributes['weight'] = self.edge_weight(graph, source, destination)
        return
    # def generate_random_graph(self):
    #     edge_count = uniform(self.EDGE_COUNT_MIN, self.EDGE_COUNT_MAX)
    #     while True:
    #         graph = gnm_random_graph(self.NODE_COUNT, 2 * edge_count, directed = True)
    #         if self.constraints_satisfied(graph):
    #             self.process_graph(graph)
    #             return graph
    def key_mapping(self, tuple_key):
        new_key = tuple_key[0] * self.RADIX + tuple_key[1]
        return new_key
    def generate_grid_graph(self):
        tuple_keyed_graph = grid_2d_graph(self.RADIX, self.RADIX)
        graph = relabel_nodes(tuple_keyed_graph, self.key_mapping)
        self.process_graph(graph)
        return graph
    def generate_watts_strogatz_graph(self):
        graph = connected_watts_strogatz_graph(self.NODE_COUNT, self.DEGREE_AVERAGE, uniform(0.1, 0.9))
        self.process_graph(graph)
        return graph
    def generate_small_world_graph(self):
        while True:
            tuple_keyed_graph = navigable_small_world_graph(self.RADIX)
            graph = relabel_nodes(tuple_keyed_graph, self.key_mapping)
            if True:
                self.process_graph(graph)
                return graph
    def weighted_length(self, traffic, graph, weight):
        raw_path_lengths = shortest_path_length(graph, weight = weight)
        path_lengths = zeros((self.NODE_COUNT, self.NODE_COUNT))
        for source in raw_path_lengths:
            for destination in raw_path_lengths[source]:
                path_lengths[source][destination] = raw_path_lengths[source][destination]
        averaged_traffic = tile(traffic, (self.NODE_COUNT,1))
        return average(path_lengths, weights = averaged_traffic)
    def load_data(self, dataset, columns):
        raw_dataset = loadtxt(dataset, usecols = columns, skiprows = 1)
        self.scaler.fit(raw_dataset)
        scaled_dataset = self.scaler.transform(raw_dataset)
        split_dataset = map(squeeze, hsplit(scaled_dataset, range(1,self.TARGET_COUNT+1)))
        return split_dataset
    def estimate_metrics(self, raw_features):
        raw_sample = asarray(range(self.TARGET_COUNT) + raw_features)
        scaled_sample = self.scaler.transform(raw_sample)
        for i in range(self.TARGET_COUNT):
            scaled_sample[i] = (self.estimators[i].predict(scaled_sample[self.TARGET_COUNT:])).tolist()[0]
        estimated_raw_sample = self.scaler.inverse_transform(asarray(scaled_sample)).tolist()
        estimated_metrics = estimated_raw_sample[:self.TARGET_COUNT]
        return estimated_metrics
    def evaluate_quality(self, raw_targets):
        if self.optimization_target == 'latency_power_product':
            return -(raw_targets[0] * raw_targets[1])
        elif self.optimization_target == 'latency':
            return -raw_targets[0]
        elif self.optimization_target == 'power':
            return -raw_targets[1]
        else:
            raise NameError('unknown optimization_target')
    def add_data(self, dataset, initial, graph):
        metrics = actuator.evaluate_metrics(graph)
        real_latency_power_product = prod(metrics)
        raw_features = self.extract_features(self.benchmark, graph)
        estimated_metrics = metrics
        if initial == False:
            estimated_metrics = self.estimate_metrics(raw_features)
        estimated_latency_power_product = prod(estimated_metrics)
        data_instance = metrics + raw_features + estimated_metrics
        data_instance += [real_latency_power_product, estimated_latency_power_product]
        print 'performer: add_data:', 'benchmark =', self.benchmark + ';', data_instance
        with open(dataset, 'a') as f:
            f.write('\t'.join(map(str, data_instance)) + '\n')
        return
    def initialize_dataset(self):
        for round in range(self.INITIAL_DATASET_SIZE):
            print 'performer: initialize_dataset: round =', round
            graph = self.generate_watts_strogatz_graph()
            self.add_data(self.file_name('dataset', self.benchmark), True, graph)
        return
    def string_to_graph(self, graph_string):
        # print 'performer: string_to_graph: graph_string =', graph_string
        graph = Graph(literal_eval(graph_string))
        performer.process_graph(graph)
        return graph
performer = Performer()

class Sensor(object):
    def extract_targets(self, simulation_log, target_tokens):
        with open(simulation_log, 'r') as f:
            target_values = copy(target_tokens)
            for line in f:
                for index in range(len(target_tokens)):
                    if line.startswith(target_tokens[index]):
                        value_string = (line.replace(target_tokens[index], '').partition(' ')[0])
                        target_values[index] = float(value_string)
        return target_values
sensor = Sensor()
    
class Actuator(object):
    SIMULATOR = 'booksim2/src/booksim'
    def configure_topology(self, graph):
        with open(performer.file_name('topology', performer.benchmark), 'w+') as f:
            for source in graph:
                connection = ['router', source, 'node', source]
                for destination in graph[source]:
                    length = performer.link_length(graph[source][destination]['weight'])
                    connection += ['router', destination, length]
                f.write(' '.join(map(str, connection)) + '\n')
        return
    def evaluate_metrics(self, graph):
        self.configure_topology(graph)
        with open(performer.file_name('simulation', performer.benchmark), 'w+') as f:
            with open('error.log', 'w+') as error_log:
                check_call([self.SIMULATOR, performer.file_name('configuration', performer.benchmark)],
                           stdout = f, stderr = error_log)
        metrics = sensor.extract_targets(performer.file_name('simulation', performer.benchmark),
                                                  performer.TARGET_TOKENS)
        return metrics
    def add_design_instance(self, architecture, graph):
        metrics = self.evaluate_metrics(graph)
        design_instance = [datetime.now(), architecture, performer.benchmark,
                           performer.optimization_target, to_dict_of_dicts(graph)] + metrics
        with open(performer.file_name('design', performer.benchmark), 'a') as f:
            f.write('\t'.join(map(str, design_instance)) + '\n')
        return
    def initialize_dataset_file(self):
        columns = (['real_' + s for s in performer.TARGET_NAMES] + performer.FEATURE_NAMES
                           + ['estimated_' + s for s in performer.TARGET_NAMES]
                           + ['real_latency_power_product', 'estimated_latency_power_product'])
        with open(performer.file_name('dataset', performer.benchmark), 'w+') as f:
            f.write('\t'.join(map(str, columns)) + '\n')
        return
    def initialize_design_file(self):
        columns = ['time', 'architecture', 'benchmark', 'optimization_target', 'topology'] + performer.TARGET_NAMES
        with open(performer.file_name('design', performer.benchmark), 'w+') as f:
            f.write('\t'.join(map(str, columns)) + '\n')
        return
    def initialize_accuracy_file(self):
        columns = ['time', 'benchmark']
        for target in ['latency', 'power']:
            for parameter in ['accuracy', 'parameters']:
                columns.append(target + '_' + parameter)
        with open(performer.file_name('accuracy'), 'w+') as f:
            f.write('\t'.join(map(str, columns)) + '\n')
        return
    def initialize_configuration_file(self):
        copyfile(performer.configuration_template, performer.file_name('configuration', performer.benchmark))
        node_string = 'hotspot({{' + ','.join(map(str, range(performer.NODE_COUNT))) + '},'
        traffic_string = '{'+ ','.join(map(str, performer.traffic[performer.benchmark].tolist())) + '}})'
        for line in input(performer.file_name('configuration', performer.benchmark), inplace = True):
            if line.startswith('packet_size ='):
                print line.replace(line, 'packet_size = ' + str(performer.packet_size) + ';')
            elif line.startswith('injection_rate ='):
                print line.replace(line, 'injection_rate = ' + str(performer.injection_rate) + ';')
            elif line.startswith('routing_delay  = '):
                print line.replace(line, 'routing_delay  = ' + str(performer.NODE_WEIGHT) + ';')
            elif line.startswith('network_file ='):
                print line.replace(line, 'network_file = '+performer.file_name('topology', performer.benchmark)+';')
            elif line.startswith('traffic ='):
                print line.replace(line, 'traffic = ' + node_string + traffic_string + ';')
            else:
                print line.replace(line, line),
        return
    def initialize_files(self):
        self.initialize_accuracy_file()
        self.initialize_design_file()
        self.initialize_dataset_file()
        self.initialize_configuration_file()
        return
    def draw_graph(self, benchmark, graph_string, network_figure):
        figure()
        title(benchmark)
        graph = performer.string_to_graph(graph_string)
        performer.process_graph(graph)
        draw(graph, get_node_attributes(graph, 'position'), hold = True)
        # draw_networkx_edge_labels(graph, get_node_attributes(graph, 'position'), alpha = 0.2)
        savefig(network_figure)
        return
    def visualize(self, dataframe, values):
        print dataframe
        axis = dataframe.plot()
        axis.set_ylabel(values)
        axis.get_figure().savefig(performer.file_name(values))
        return
    def compare(self, dataframe, index, columns, values):
        feature = dataframe[[index, columns, values]]
        print feature
        feature = feature.pivot(index, columns, values)
        actuator.visualize(feature, values)
        return
    def plot_histogram(self, dataframe, column, value):
        figure()
        print dataframe[[column, value]]
        distributions = DataFrame()
        for index1, row in dataframe.iterrows():
            bin_count = max(row[value]) + 3
            print bin_count
            new_column = DataFrame({row[column]: Series(histogram(row[value], bins = range(bin_count))[0])})
            distributions = concat([distributions, new_column], axis = 1)
        axis = distributions.plot()
        axis.set_xlabel(value)
        axis.get_figure().savefig(performer.file_name(value))
        return
actuator = Actuator()

class Optimization(SearchProblem):
    def actions(self, state):
        performer.add_data(performer.file_name('dataset', performer.benchmark), False, state)
        successors = []
        for cluster in combinations(nodes(state),2):
            successor = state.copy()
            for node_pair in combinations(cluster,2):
                if node_pair[1] in successor.neighbors(node_pair[0]):
                    successor.remove_edge(node_pair[0],node_pair[1])
                else:
                    successor.add_edge(node_pair[0], node_pair[1],
                                       weight = performer.edge_weight(state, node_pair[0], node_pair[1]))
            if performer.constraints_satisfied(successor):
                successors.append(successor)
        if not successors:
            print 'no successors!'
        return successors
    def result(self, state, action):
        return action
    def value(self, state):
        raw_features = performer.extract_features(performer.benchmark, state)
        estimated_metrics = performer.estimate_metrics(raw_features)
        estimated_quality = performer.evaluate_quality(estimated_metrics)
        return estimated_quality

def initialize(benchmark):
    performer.initialize_benchmark(benchmark)
    actuator.initialize_files()
    performer.initialize_dataset()
    return

def design_freenet(benchmark):
    performer.initialize_benchmark(benchmark)
    restarts = 100
    iterations = 200
    for trial in range(restarts):
        print 'design_freenet:', 'benchmark =', performer.benchmark + ';',
        print 'trial =', trial
        performer.update_estimators(4)
        optimization = Optimization(initial_state = performer.generate_small_world_graph())
        final = hill_climbing(optimization, iterations_limit = iterations)
        graph = final.state
        actuator.add_design_instance('freenet', graph)
    return

def design_small_world(benchmark):
    performer.initialize_benchmark(benchmark)
    print 'design_small_world: ' + performer.benchmark
    graph = performer.generate_small_world_graph()
    actuator.add_design_instance('small_world', graph)
    return

def design_mesh(benchmark):
    performer.initialize_benchmark(benchmark)
    print 'design_mesh: ' + performer.benchmark
    graph = performer.generate_grid_graph()
    actuator.add_design_instance('mesh', graph)
    return

def analyze():
    # metrics = ['latency', 'power', 'latency_power_product']
    metrics = ['power']
    results = DataFrame()
    for benchmark in performer.benchmarks:
        data = read_csv(performer.file_name('design', benchmark), sep = '\t', skipinitialspace = True)
        for architecture in ['mesh', 'small_world', 'freenet']:
            architecture_data = data[data['architecture'] == architecture]
            record = architecture_data.ix[architecture_data[metrics].idxmin()]
            results = results.append(record, ignore_index = True)
    results['graph'] = [performer.string_to_graph(t) for t in results['topology']]
    results['energy'] = results['power'] * 7.511e-8
    results['latency_energy_product'] = results['latency'] * results['energy']
    results['edge_count'] = [number_of_edges(g) for g in results['graph']]
    results['path_lengths'] = [[length for d in shortest_path_length(g, weight = 'weight').values()
                                for length in d.values()] for g in results['graph']]
    results['path_length_average'] = [average(h) for h in results['path_lengths']]
    results['path_length_max'] = [max(h) for h in results['path_lengths']]
    results['hop_counts'] = [[length for d in shortest_path_length(g).values()
                              for length in d.values()] for g in results['graph']]
    results['hop_count_average'] = [average(h) for h in results['hop_counts']]
    results['hop_count_max'] = [max(h) for h in results['hop_counts']]
    results['diameter'] = [diameter(g) for g in results['graph']]
    results['radius'] = [radius(g) for g in results['graph']]
    results['link_lengths'] = [[performer.link_length(w) for w in get_edge_attributes(g, 'weight').values()]
                               for g in results['graph']]
    results['link_length_average'] = [average(h) for h in results['link_lengths']]
    results['link_length_max'] = [max(h) for h in results['link_lengths']]
    results['degrees'] = [g.degree().values() for g in results['graph']]
    results['degree_average'] = [average(d) for d in results['degrees']]
    results['degree_max'] = [max(d) for d in results['degrees']]
    results['degree_norm'] = [norm(d)**2 for d in results['degrees']]
    results['network_figure'] = [performer.file_name('network_figure', b) for b in results['benchmark']]
    results['architecture/benchmark'] = results['architecture'] + '/' + results['benchmark']
    # results.sort('energy', inplace = True)
    print 'analyze :', results.columns.values
    attributes = ['path_lengths', 'hop_counts', 'link_lengths']
    mask = (results['benchmark'] == 'fft') & (results['architecture'] == 'mesh')
    mask = (results['architecture'] == 'freenet')
    mask = (results['benchmark'] == 'fft')
    for attribute in attributes:
        actuator.plot_histogram(results[mask], 'architecture/benchmark', attribute)
    # attributes = ['latency', 'energy', 'latency_energy_product', 'path_length_average', 'hop_count_average',
    #               'link_length_average']
    # for attribute in attributes:
    #     actuator.compare(results, 'benchmark', 'architecture', attribute)
    # freenet_topologies = results[results['architecture'] == 'freenet']
    # map(actuator.draw_graph, freenet_topologies['benchmark'],
    #     freenet_topologies['topology'], freenet_topologies['network_figure'])
    return

if __name__ == '__main__':
    # performer.initialize_optimization_target('power')
    # pool = Pool(8)
    # pool.map(initialize, performer.benchmarks)
    # pool.map(design_mesh, performer.benchmarks)
    # pool.map(design_small_world, performer.benchmarks)
    # pool.map(design_freenet, performer.benchmarks)
    # initialize('fft')
    # design_mesh('fft')
    # design_small_world('fft')
    # design_freenet('fft')
    analyze()
    # graph = performer.generate_small_world_graph()
    # pprint(graph.nodes(data = True))
    # pprint(graph.edges(data = True))
