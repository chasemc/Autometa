#!/usr/bin/env nextflow

nextflow.enable.dsl = 2

// Input
params.kingdom = "bacteria"
params.length_cutoff = 3000
params.kmer_size = 4
params.metagenome = "</path/to/metagenome.fna>"

// Where to store intermediate and final results:
params.interim = "</path/to/directory/to/store/user/interimediate/results>"
params.processed = "</path/to/directory/to/store/user/final/results>"

// Databases
params.ncbi_database = "$HOME/Autometa/autometa/databases/ncbi"
params.diamond_database = "$HOME/Autometa/autometa/databases/ncbi/nr.dmnd"
params.markers_database = "$HOME/Autometa/autometa/databases/markers"
// Additional runtime settings
params.cpus = 2


log.info """

 Autometa - Automated Extraction of Genomes from Shotgun Metagenomes
 =====================================================
 projectDir          : ${workflow.projectDir}
 -----------------------------------------------------
 Data
 -----------------------------------------------------
 metagenome          : ${params.metagenome}
 interim             : ${params.interim}
 processed           : ${params.processed}
 -----------------------------------------------------
 Parameters
 -----------------------------------------------------
 length_cutoff       : ${params.length_cutoff}
 kmer_size           : ${params.kmer_size}
 kingdom             : ${params.kingdom}
 -----------------------------------------------------
 Databases
 -----------------------------------------------------
 ncbi_database       : ${params.ncbi_database}
 diamond_database    : ${params.diamond_database}
 markers_database    : ${params.markers_database}
 -----------------------------------------------------
"""

// Note: It is required to include these processes after parameter definitions
// so they take on the provided values
include { LENGTH_FILTER; KMERS; COVERAGE; ORFS; MARKERS } from './nextflow/common-tasks.nf'
include { TAXON_ASSIGNMENT } from './nextflow/taxonomy-tasks.nf'
include { BINNING; UNCLUSTERED_RECRUITMENT } from './nextflow/binning-tasks.nf'

// Just placing some ideas here as how you would want to modularize the workflows into the main Autometa pipeline.

workflow {
  take:
    path metagenome
    // We have had to deal with multiple scenarios here where the user has to separately provide coverage information
    // Either they provide the coverage table of their coverage calculations
    // *or*
    //  we perform the coverage calculations with the reads they used to perform the assembly.
    path coverage
    path reads

  main:
    // Perform various annotations on provided metagenome
    LENGTH_FILTER(metagenome)
    COVERAGE(LENGTH_FILTER.out)
    ORFS(LENGTH_FILTER.out)
    MARKERS(ORFS.out.prots)
    // Perform taxon assignment with filtered metagenome
    TAXON_ASSIGNMENT(LENGTH_FILTER.out, ORFS.out.prots)
    // Now perform binning with all of our annotations.
    KMERS(TAXON_ASSIGNMENT.out.bacteria)
    // KMERS(TAXON_ASSIGNMENT.out.archaea) ... for case of performing binning on archaea
    BINNING(KMERS.out.normalized, COVERAGE.out, MARKERS.out, TAXON_ASSIGNMENT.out.taxonomy)
    // Then unclustered recruitment of any unclustered contigs using binning assignments from above.
    UNCLUSTERED_RECRUITMENT(KMERS.out.normalized, COVERAGE.out, BINNING.out, MARKERS.out, TAXON_ASSIGNMENT.out.taxonomy)

  emit:
    binning = BINNING.out.binning
    recruitment = UNCLUSTERED_RECRUITMENT.out
    all_binning_results = BINNING.out | mix(UNCLUSTERED_RECRUITMENT.out) | collect
}


/*
 * completion handler
 */
workflow.onComplete {
	log.info ( workflow.success ? "\nDone!\n" : "Oops .. something went wrong" )
}