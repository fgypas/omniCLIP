"""
    omniCLIP is a CLIP-Seq peak caller

    Copyright (C) 2017 Philipp Boss

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

from collections import defaultdict
from intervaltree import IntervalTree
import numpy as np
from scipy.sparse import csr_matrix


def mask_miRNA_positions(Sequences, GeneAnnotation):
    """
    This function takes the sequences and
    the gene annotation and sets all counts in Sequences to zero that overlap
    miRNAs in the gene annotaion
    """
    keys = ['Coverage', 'Read-ends', 'Variants']
    # Create a dictionary that stores the genes in the Gene annnotation
    gene_dict = {}

    for gene in GeneAnnotation.features_of_type('gene'):
        gene_dict[gene.id.split('.')[0]] = gene

    # Get Chromosomes:
    genes_chr_dict = defaultdict(list)
    for gene in list(gene_dict.values()):
        genes_chr_dict[gene.chrom].append(gene)

    # Create an interval tree for the genes:
    interval_chr_dict = {}
    for chr in list(genes_chr_dict.keys()):
        interval_chr_dict[chr] = IntervalTree()
        for gene in genes_chr_dict[chr]:
            interval_chr_dict[chr][gene.start:gene.stop] = gene

    # Iterate over the genes in the Sequences:
    miRNAs = [miRNA for miRNA in GeneAnnotation.features_of_type('gene') if miRNA.attributes.get('gene_type').count('miRNA') > 0]
    for miRNA in miRNAs:
        curr_chr = miRNA.chrom
        curr_genes = sorted(interval_chr_dict[curr_chr][miRNA.start:miRNA.stop])
        curr_genes = [gene[2] for gene in curr_genes]

        # Get the miRNAs that overalp:
        for curr_gene_obj in curr_genes:
            curr_gene = curr_gene_obj.id.split('.')[0]

            # Get position relative to the host gene
            curr_start = max(0, miRNA.start - gene_dict[curr_gene].start)
            curr_stop = max(gene_dict[curr_gene].stop - gene_dict[curr_gene].start, miRNA.stop - gene_dict[curr_gene].start)

            # Set for each field the sequences to zeros
            for curr_key in keys:
                if curr_key in Sequences:
                    if curr_key in Sequences[curr_gene]:
                        for rep in list(Sequences[curr_gene][curr_key].keys()):
                            if curr_key == 'Variants':
                                # Convert the Variants to array
                                curr_seq = csr_matrix((Sequences[curr_gene]['Variants'][rep]['data'][:], Sequences[curr_gene]['Variants'][rep]['indices'][:],
                                    Sequences[curr_gene]['Variants'][rep]['indptr'][:]), shape=Sequences[curr_gene]['Variants'][rep]['shape'][:])

                                ix_slice = np.logical_and(curr_start <= curr_seq.indices, curr_seq.indices < curr_stop)
                                Sequences[curr_gene]['Variants'][rep]['data'][ix_slice] = 0
                            else:
                                curr_seq = Sequences[curr_gene][curr_key][rep][:, :]
                                curr_seq[:, curr_start: curr_stop] = 0
                                Sequences[curr_gene][curr_key][rep][:, :] = curr_seq

    return Sequences


def mark_overlapping_positions(Sequences, GeneAnnotation):
    """
    This function takes the sequences and
    the gene annotation and adds to Sequences a track that indicates the overlaping regions
    """

    # Add fields to Sequence structure:
    for gene in list(Sequences.keys()):
        Sequences[gene].create_group('mask')
        rep = list(Sequences[gene]['Coverage'].keys())[0]
        if rep == '0':
            Sequences[gene]['mask'].create_dataset(rep, data=np.zeros(Sequences[gene]['Coverage'][rep][()].shape), compression="gzip", compression_opts=9, chunks=Sequences[gene]['Coverage'][rep][()].shape, dtype='i8')

    # Create a dictionary that stores the genes in the Gene annnotation
    gene_dict = {}

    for gene in GeneAnnotation.features_of_type('gene'):
        gene_dict[gene.id.split('.')[0]] = gene

    # Get Chromosomes:
    genes_chr_dict = defaultdict(list)
    for gene in list(gene_dict.values()):
        genes_chr_dict[gene.chrom].append(gene)

    # Create an interval tree for the genes:
    interval_chr_dict = {}
    for chr in list(genes_chr_dict.keys()):
        interval_chr_dict[chr] = IntervalTree()
        for gene in genes_chr_dict[chr]:
            interval_chr_dict[chr][gene.start:gene.stop] = gene

    genes = [gene for gene in GeneAnnotation.features_of_type('gene')]

    # Iterate over the genes in the Sequences:
    for gene in genes:
        if not (gene.id.split('.')[0] in Sequences):
            continue
        curr_chr = gene.chrom
        curr_genes = sorted(interval_chr_dict[curr_chr][gene.start:gene.stop])
        curr_genes = [curr_gene[2] for curr_gene in curr_genes]
        curr_genes.remove(gene)
        # Get the genes that overalp:
        for curr_gene_obj in curr_genes:
            curr_gene = curr_gene_obj.id.split('.')[0]

            # Get position of overlapping gene relative to the host gene
            ovrlp_start = max(0, gene_dict[curr_gene].start - gene.start)
            ovrlp_stop = min(gene.stop - gene.start, gene_dict[curr_gene].stop - gene.start)

            # Set for each field the sequences to zeros
            rep = list(Sequences[gene.id.split('.')[0]]['Coverage'].keys())[0]
            Sequences[gene.id.split('.')[0]]['mask'][rep][0, ovrlp_start:ovrlp_stop] = True

    return Sequences
