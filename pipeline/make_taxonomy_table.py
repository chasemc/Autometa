#!/usr/bin/env python

import subprocess
import argparse
import os
import pandas as pd
from Bio import SeqIO
import sys
import urllib2

def cythonize_lca_functions():
	logger.info("{}/lca_functions.so not found, cythonizing lca_function.pyx for make_taxonomy_table.py".format(pipeline_path))
	subprocess.call("cd {}".format(pipeline_path), shell=True)
	subprocess.call("./setup_lca_functions.py build_ext --inplace", shell = True)
	subprocess.call("cd {}".format(output_dir), shell=True)

def download_file(destination_dir, file_url, md5_url):
	filename = file_url.split('/')[-1]
	md5name = md5_url.split('/')[-1]

	md5check = False
	
	while md5check == False:
		os.system('wget %s -O %s' % (file_url, destination_dir + '/' + filename))
		os.system('wget %s -O %s' % (md5_url, destination_dir + '/' + md5name))

		downloaded_md5 = subprocess.check_output(['md5sum', destination_dir + '/' + filename]).split(' ')[0]

		with open(destination_dir + '/' + md5name, 'r') as check_md5_file:
			check_md5 = check_md5_file.readline().split(' ')[0]

		if downloaded_md5 == check_md5:
			md5check = True

def md5IsCurrent(local_md5_path, remote_md5_url):
	remote_md5_handle = urllib2.urlopen(remote_md5_url)
	remote_md5 = remote_md5_handle.readline().split(' ')[0]

	with open(local_md5_path, 'r') as local_md5_file:
		local_md5 = local_md5_file.readline().split(' ')[0]

	if local_md5 == remote_md5:
		return True
	else:
		return False

def update_dbs(database_path, db='all'):
	"""Updates databases for AutoMeta usage"""
	taxdump_url = "ftp://ftp.ncbi.nlm.nih.gov/pub/taxonomy/taxdump.tar.gz"
	taxdump_md5_url = taxdump_url+".md5"
	accession2taxid_url = "ftp://ftp.ncbi.nih.gov/pub/taxonomy/accession2taxid/prot.accession2taxid.gz"
	accession2taxid_md5_url = accession2taxid_url+".md5"
	nr_db_url = "ftp://ftp.ncbi.nlm.nih.gov/blast/db/FASTA/nr.gz"
	nr_db_md5_url = nr_db_url+".md5"
	#Downloading files for db population
	if db == 'all' or db == 'nr':
		# First download nr if we don't yet have it OR it is not up to date
		if os.path.isfile(database_path + '/nr.gz.md5'):
			if not md5IsCurrent(database_path + '/nr.gz.md5', nr_db_md5_url):
				print("updating nr.dmnd")
				download_file(database_path, nr_db_url, nr_db_md5_url)
		else:
			print("updating nr.dmnd")
			download_file(database_path, nr_db_url, nr_db_md5_url)

		# Now we make the diamond database
		if not (os.path.isfile(database_path + '/nr.dmnd') and os.path.isfile(databse_path + '/nr.dmnd.md5')):
			print("building nr.dmnd database, this may take some time")
			subprocess.call("diamond makedb --in {} --db {}/nr".format(database_path+'/nr.gz', database_path), shell = True)
			#Make an md5 file to signal that we have built the database successfully
			subprocess.call('md5sum ' + database_path + '/nr.dmnd > ' + database_path + '/nr.dmnd.md5')
			os.system('rm %s/nr.gz' % database_path)
			print("nr.dmnd updated")
	if db == 'all' or db == 'acc2taxid':
		# Download prot.accession2taxid.gz only if the version we have is not current
		if os.path.isfile(database_path + '/prot.accession2taxid.gz.md5'):
			if not md5IsCurrent(database_path + '/prot.accession2taxid.gz.md5', accession2taxid_md5_url):
				print("updating prot.accession2taxid")
				download_file(database_path, accession2taxid_url, accession2taxid_md5_url)
		else:
			print("updating prot.accession2taxid")
			download_file(database_path, accession2taxid_url, accession2taxid_md5_url)

		if os.path.isfile(database_path + '/prot.accession2taxid.gz'):
			print("Gunzipping prot.accession2taxid gzipped file\nThis may take some time...")
			os.system('gunzip -9vNf %s.gz > %s' % (database_path + '/prot.accession2taxid.gz', database_path + '/prot.accession2taxid'))
			print("prot.accession2taxid updated")
	if db == 'all' or db == 'taxdump':
		# Download taxdump only if the version we have is not current
		if os.path.isfile(database_path + '/taxdump.tar.gz.md5'):
			if not md5IsCurrent(database_path + '/taxdump.tar.gz.md5', taxdump_md5_url):
				print("updating nodes.dmp and names.dmp")
				download_file(database_path, taxdump_url, taxdump_md5_url)
		else:
			print("updating nodes.dmp and names.dmp")
			download_file(database_path, taxdump_url, taxdump_md5_url)

		if os.path.isfile(database_path + '/taxdump.tar.gz'):
			os.system('tar -xzf %s/taxdump.tar.gz -C %s names.dmp nodes.dmp' % (database_path, database_path))
			os.system('rm %s/taxdump.tar.gz' % database_path)
			print("nodes.dmp and names.dmp updated")

def length_trim(fasta_path,fasta_prefix,length_cutoff):
	#Trim the length of fasta file
	outfile_name = str(fasta_prefix) + "_filtered.fasta"
	subprocess.call("{}/fasta_length_trim.pl {} {} {}".format(pipeline_path, fasta_path, length_cutoff, outfile_name), shell = True)
	return outfile_name

def run_prodigal(path_to_assembly):
	#When "shell = True", need to give one string, not a list
	prodigal_output = path_to_assembly.split('.')[0] + '.orfs.faa'
	if os.path.isfile(prodigal_output):
		print "{} file already exists!".format(prodigal_output)
		print "Continuing to next step..."
	else:
		subprocess.call(" ".join(['prodigal ','-i ' + path_to_assembly, '-a ' + path_to_assembly.split(".")[0] +\
	 	'.orfs.faa','-p meta', '-m', '-o ' + path_to_assembly.split(".")[0] + '.txt']), shell = True)

def run_diamond(prodigal_output, diamond_db_path, num_processors, prodigal_daa):
	view_output = prodigal_output + ".tab"
	current_dir = os.getcwd()
	tmp_dir_path = current_dir + '/tmp'
	if not os.path.isdir(tmp_dir_path):
		os.makedirs(tmp_dir_path) # This will give an error if the path exists but is a file instead of a dir
	subprocess.call("diamond blastp --query {}.faa --db {} --evalue 1e-5 --max-target-seqs 200 -p {} --daa {} -t {}".format(prodigal_output, diamond_db_path, num_processors, prodigal_daa,tmp_dir_path), shell = True)
	subprocess.call("diamond view -a {} -f tab -o {}".format(prodigal_daa, view_output), shell = True)
	return view_output

#blast2lca using accession numbers#
def run_blast2lca(input_file, taxdump_path):
	output = input_file.rstrip(".tab") + ".lca"
	if os.path.isfile(output):
		print "{} file already exists!".format(output)
		print "Continuing to next step..."
	else:
		subprocess.call("{}/lca.py database_directory {} {} > {}".format(pipeline_path, db_dir_path, input_file, output), shell = True)
	return output

def run_taxonomy(pipeline_path, assembly_path, tax_table_path, db_dir_path,coverage_table): #Have to update this
	initial_table_path = assembly_path + '.tab'

	# Only make the contig table if it doesn't already exist
	if not os.path.isfile(initial_table_path):
		if coverage_table:
			subprocess.call("{}/make_contig_table.py -a {} -o {} -c {}".format(pipeline_path, assembly_path, initial_table_path,coverage_table), shell = True)
		else:
			subprocess.call("{}/make_contig_table.py -a {} -o {}".format(pipeline_path, assembly_path, initial_table_path), shell = True)

	if coverage_table:		
		subprocess.call("{}/add_contig_taxonomy.py {} {} {} taxonomy.tab".format(pipeline_path, initial_table_path, tax_table_path, db_dir_path), shell = True)
	else:
	   subprocess.call("{}/add_contig_taxonomy.py {} {} {} taxonomy.tab".format(pipeline_path, initial_table_path, tax_table_path, db_dir_path), shell = True)
	return 'taxonomy.tab'

pipeline_path = sys.path[0]
pathList = pipeline_path.split('/')
pathList.pop()
autometa_path = '/'.join(pathList)

#argument parser
parser = argparse.ArgumentParser(description="Script to generate the contig taxonomy table.", epilog="Output will be directed to recursive_dbscan.py")
parser.add_argument('-a', '--assembly', metavar='<assembly.fasta>', help='Path to metagenomic assembly fasta', required=True)
parser.add_argument('-p', '--processors', metavar='<int>', help='Number of processors to use.', type=int, default=1)
parser.add_argument('-db', '--db_dir', metavar='<dir>', help='Path to directory with taxdump, protein accessions and diamond (NR) protein files. If this path does not exist, will create and download files.', required=False, default=autometa_path + '/databases')
parser.add_argument('-l', '--length_cutoff', metavar='<int>', help='Contig length cutoff to consider for binning in bp', default=10000, type = int)
parser.add_argument('-u', '--update', required=False, action='store_true',\
 help='Checks/Adds/Updates: nodes.dmp, names.dmp, accession2taxid, nr.dmnd files within specified directory.')
parser.add_argument('-v', '--cov_table', metavar='<coverage.tab>', help="Path to coverage table made by calculate_read_coverage.py. If this is not specified then coverage information will be extracted from contig names (SPAdes format)", required=False)

args = vars(parser.parse_args())

db_dir_path = args['db_dir'].rstrip('/')
num_processors = args['processors']
length_cutoff = args['length_cutoff']
fasta_path = args['assembly']
fasta_assembly_prefix = os.path.splitext(os.path.basename(args['assembly']))[0]
prodigal_output = fasta_assembly_prefix + "_filtered.orfs"
prodigal_daa = prodigal_output + ".daa"
#add_contig_path = pipeline_path
filtered_assembly = fasta_assembly_prefix + "_filtered.fasta"
cov_table = args['cov_table']

if not os.path.isfile(pipeline_path+"/lca_functions.so"):
	cythonize_lca_functions()

if not os.path.isdir(db_dir_path):
	#Verify the 'Autometa databases' directory exists
	print('No databases directory found, creating and populating AutoMeta databases directory\nThis may take some time...')
	os.system('mkdir {}'.format(db_dir_path))
	update_dbs(db_dir_path)
elif not os.listdir(db_dir_path):
	#The 'Autometa databases' directory is empty
	print('AutoMeta databases directory empty, populating with appropriate databases.\nThis may take some time...')
	update_dbs(db_dir_path)
elif not (os.path.isfile(db_dir_path + '/nr.dmnd') or os.path.isfile(db_dir_path + '/nr.dmnd.md5') or os.path.isfile(db_dir_path + '/nr.gz.md5')):
	print('NR database not found, downloading and building DIAMOND database.\nThis may take some time...')
	update_dbs(db_dir_path, 'nr')
elif not (os.path.isfile(db_dir_path + '/prot.accession2taxid') or os.path.isfile(db_dir_path + '/prot.accession2taxid.gz.md5')):
	print('acc2taxid files not found, downloading.\nThis may take some time...')
	update_dbs(db_dir_path, 'acc2taxid')
elif not (os.path.isfile(db_dir_path + '/names.dmp') or os.path.isfile(db_dir_path + '/nodes.dmp') or os.path.isfile(db_dir_path + '/taxdump.tar.gz.md5')):
	print('Taxdump files not found, downloading.\nThis may take some time...')
	update_dbs(db_dir_path, 'taxdump')

names_dmp_path = db_dir_path + '/names.dmp'
nodes_dmp_path = db_dir_path + '/nodes.dmp'
accession2taxid_path = db_dir_path + '/prot.accession2taxid'
diamond_db_path = db_dir_path + '/nr.dmnd'
current_taxdump_md5 = db_dir_path + '/taxdump.tar.gz.md5'
current_acc2taxid_md5 = db_dir_path + '/prot.accession2taxid.gz.md5'
current_nr_md5 = db_dir_path + '/nr.gz.md5'

if args['update']:
	print("Checking database directory for updates")
	update_dbs(db_dir_path, 'all')

if not os.path.isfile(prodigal_output + ".faa"):
	print "Prodigal output not found. Running prodigal..."
	#Check for file and if it doesn't exist run make_marker_table
	length_trim(fasta_path, fasta_assembly_prefix, length_cutoff)
	run_prodigal(filtered_assembly)

if not os.path.isfile(prodigal_output + ".daa"):
	print "Could not find {}. Running diamond blast... ".format(prodigal_output + ".daa")
	diamond_output = run_diamond(prodigal_output, diamond_db_path, num_processors, prodigal_daa)
elif os.stat(prodigal_output + ".daa").st_size == 0:
	print "{} file is empty. Re-running diamond blast...".format(prodigal_output + ".daa")
	diamond_output = run_diamond(prodigal_output, diamond_db_path, num_processors, prodigal_daa)
else:
	diamond_output = prodigal_output + ".tab"

if not os.path.isfile(prodigal_output + ".lca"):
	print "Could not find {}. Running lca...".format(prodigal_output + ".lca")
	blast2lca_output = run_blast2lca(diamond_output,db_dir_path)
elif os.stat(prodigal_output + ".lca").st_size == 0:
	print "{} file is empty. Re-running lca...".format(prodigal_output + ".lca")
	blast2lca_output = run_blast2lca(diamond_output,db_dir_path)
else:
	blast2lca_output = prodigal_output + ".lca"

print "Running add_contig_taxonomy.py... "
taxonomy_table = run_taxonomy(pipeline_path, filtered_assembly, blast2lca_output, db_dir_path, cov_table)

# Split the original contigs into sets for each kingdom
taxonomy_pd = pd.read_table(taxonomy_table)
categorized_seq_objects = {}
all_seq_records = {}

# Load fasta file
for seq_record in SeqIO.parse(filtered_assembly, 'fasta'):
	all_seq_records[seq_record.id] = seq_record

for i, row in taxonomy_pd.iterrows():
	kingdom = row['kingdom']
	contig = row['contig']
	if kingdom in categorized_seq_objects:
		categorized_seq_objects[kingdom].append(all_seq_records[contig])
	else:
		categorized_seq_objects[kingdom] = [ all_seq_records[contig] ]

# Now we write the component fasta files
for kingdom in categorized_seq_objects:
	seq_list = categorized_seq_objects[kingdom]
	output_path = kingdom + '.fasta'
	SeqIO.write(seq_list, output_path, 'fasta')

print "Done!"
