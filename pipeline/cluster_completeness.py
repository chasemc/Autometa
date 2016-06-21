#!/usr/bin/env python

# Program that determines the completeness of clusters called by dbscan

import sys
import argparse 
from Bio import SeqIO
import pdb

def assess_assembly(seq_record_list):
	assembly_size = sum(len(seq) for seq in seq_record_list)
	number_of_sequences = len(seq_record_list)
	sorted_seqs = sorted(seq_record_list, key=len)
	largest_sequence_length = len(sorted_seqs[-1])
	sequence_total = 0
	n50 = None
	for i,seq_object in enumerate(sorted_seqs):
		sequence_total += len(seq_object)
		if sequence_total > (float(assembly_size)/2):
			n50 = len(seq_object)
			break
	return { 'size': assembly_size, 'number_sequences': number_of_sequences, 'largest_sequence': largest_sequence_length, 'n50': n50 }

parser = argparse.ArgumentParser(description='Script to determine the completeness of clusters called by dbscan')
parser.add_argument('-d','--dbscantable', help='table containing dbscan information', required=True)
parser.add_argument('-c','--column', help='bin column name in dbscan table', default = 'db.cluster')
parser.add_argument('-m','--markertable', help='marker table created with make_marker_table', required=True)
parser.add_argument('-f','--fasta', help='contig fasta file', required=True)
parser.add_argument('-o','--output', help='output directory for summary table and cluster fasta files', required=True)
parser.add_argument('-k','--kingdom', help='kingdom (bacteria|archaea)', default = 'bacteria')
args = vars(parser.parse_args())

dbscan_table_path = args['dbscantable']
cluster_column_heading = args['column']
marker_table_path = args['markertable']
fasta_file_path = args['fasta']
output_prefix = args['output']
kingdom = args['kingdom']

# Input varification *TO DO*
# Check paths exist
# Check that kingdom is either 'bacteria' or 'archaea'

# First go through marker table
contig_markers = {}
marker_table = open(marker_table_path, 'r')
marker_table_rows = marker_table.read().splitlines()
marker_table.close

for i,line in enumerate(marker_table_rows):
	if i > 0:
		line_list = line.split('\t')
		pfam_list = line_list[1].split(',')
		contig = line_list[0]
		if contig not in contig_markers:
			contig_markers[contig] = {}

		for pfam in pfam_list:
			if pfam in contig_markers[contig]:
				contig_markers[contig][pfam] += 1
			else:
				contig_markers[contig][pfam] = 1

# Now go through dbscan table
dbscan_table = open(dbscan_table_path, 'r')
dbscan_table_rows = dbscan_table.read().splitlines()
dbscan_table.close

dbscan_header_line = dbscan_table_rows[0]
dbscan_header_list = dbscan_header_line.split('\t')
cluster_index = None
contig_index = None
cluster_column_found = 0
contig_column_found = 0
for i, heading in enumerate(dbscan_header_list):
	if heading == cluster_column_heading:
		cluster_index = i
		cluster_column_found += 1
	if heading == 'contig':
		contig_index = i
		contig_column_found += 1

if cluster_index is None:
	print 'Error, could not find column ' + cluster_column_heading + ' in dbscan table ' + dbscan_table_path
	sys.exit(2)

if cluster_column_found > 1:
	print 'Error, multiple columns called ' + cluster_column_heading + ' found in ' + dbscan_table_path
	sys.exit(2)

if contig_index is None:
	print 'Error, could not find contig column in ' + dbscan_table_path
	sys.exit(2)

if contig_column_found > 1:
	print 'Error, multiple contig columns found in ' + dbscan_table_path
	sys.exit(2)

cluster_contigs = {} # Keyed by contig, stores the cluster of each contig
markers_in_cluster = {} # Keyed by cluster, holds totals of each marker found

for i,line in enumerate(dbscan_table_rows):
	if i > 0:
		line_list = line.split('\t')
		contig = line_list[contig_index]
		
		cluster = line_list[cluster_index]
		cluster_contigs[contig] = cluster
		if cluster not in markers_in_cluster:
			markers_in_cluster[cluster] = {}

		#pdb.set_trace()
		if contig != "contig":
			for pfam in contig_markers[contig]:
				if pfam in markers_in_cluster[cluster]:
					markers_in_cluster[cluster][pfam] += contig_markers[contig][pfam]
				else:
					markers_in_cluster[cluster][pfam] = contig_markers[contig][pfam]

# Load fasta file using biopython
# Split into clusters
cluster_sequences = {} # Keyed by cluster, will hold lists of seq objects
for seq_record in SeqIO.parse(fasta_file_path, 'fasta'):
	seq_name = seq_record.id
	cluster = None
	if seq_name in cluster_contigs:
		cluster = cluster_contigs[seq_name]
	else:
		cluster = 'unclaimed'

	if cluster not in cluster_sequences:
		cluster_sequences[cluster] = []
	cluster_sequences[cluster].append(seq_record)

# Now go through cluster and output table
summary_table_path = output_prefix + '/summary_table'
summary_table = open(summary_table_path, 'w')
summary_table.write('cluster\tsize\tlongest_contig\tn50\tnumber_contigs\tcompleteness\tpurity\n')

for cluster in cluster_sequences:
	attributes = assess_assembly(cluster_sequences[cluster])
	if kingdom == 'bacteria':
		total_markers = 139
	else:
		total_markers = 162

	number_unique_markers = 0
	number_of_markers_found = len(markers_in_cluster[cluster])
	for pfam in markers_in_cluster[cluster]:
		if markers_in_cluster[cluster][pfam] == 1:
			number_unique_markers += 1

	completeness = (float(number_of_markers_found)/total_markers) * 100
	purity = (float(number_unique_markers)/number_of_markers_found) * 100

	# Add line to summary table
	summary_table.write(str(cluster) + '\t' + str(attributes['size']) + '\t' + str(attributes['largest_sequence']) + '\t' + str(attributes['n50']) + '\t' + str(attributes['number_sequences']) + '\t' + str(completeness) + '\t' + str(purity) + '\n')

	# Now output the fasta file
	fasta_output_path = output_prefix + '/cluster_' + cluster + '.fasta'
	SeqIO.write(cluster_sequences[cluster], fasta_output_path, 'fasta')


