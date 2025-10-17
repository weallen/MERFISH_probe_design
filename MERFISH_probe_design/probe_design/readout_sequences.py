#!/usr/bin/env python3


from multiprocessing import Pool
import numpy as np
import pandas as pd

def append_on_bit_ids_to_readout_sequences(readout_seqs:pd.core.frame.DataFrame, bit_names:str):
    '''Append a column of on-bit ids to the readout sequence table.
    Arguments:
        readout_seqs: Readout sequences for all bits in a data frame.
        bit_names: A list of bit names that specifies the on-bit positions of each readout sequence.
    '''
    on_bits = []
    for b_i in readout_seqs['id']:
        on_bits.append(bit_names.index(b_i))
    
    readout_seqs['on-bit'] = pd.Series(on_bits, index=readout_seqs.index)

def barcode_to_on_bits(barcode:str):
    '''Return a list of on-bits for a given barcode.'''
    return [i for i in range(len(barcode)) if barcode[i] == '1']

def on_bits_to_barcodes(on_bits:list, barcode_length:int):
    '''Return a barcode string given its on-bits and length.'''
    return ''.join(['1' if i in on_bits else '0' for i in range(barcode_length)])

def add_readout_seqs_to_probes_of_transcript_random(probe_table:pd.core.frame.DataFrame, 
                                                    readout_seqs:pd.core.frame.DataFrame,
                                     barcode:str, N_readout_per_probe:int, spacer:str='',
                                     each_probe_1_on_bit:bool=False):
    '''Add readout sequences to probes in a table by randomly choose
    on-bits for this transcript.
    Arguments:
        probe_table: A data frame of probes of a transcript.
        readout_seqs: The data frame of readout sequences with their on-bit positions.
        barcode: The barcode of this transcript.
        N_readout_per_probe: Number of readout sequences to be added to each probe.
        spacer: The sequence to be added between readout sequences and target sequences.
        each_probe_1_on_bit: Force each probe to have only one on-bit.
    Return:
        The updated table.
    '''
    # Re-seed the generator for each thread
    np.random.seed()

    # Initialize a dictionary that maps the on-bits to readout sequences
    on_bits = barcode_to_on_bits(barcode)
    on_bit_dict = {}
    for ob in on_bits:
        entry = readout_seqs[readout_seqs['on-bit'] == ob].iloc[0]
        on_bit_dict[ob] = (entry['id'], entry['sequence'])

    # Randomly add readout sequences to all probes
    probe_barcodes = []
    readout_probe_names = []
    sequences = []
    # sort by shift:
    probe_table = probe_table.sort_values(by='shift')
    for i, row in probe_table.iterrows():
        # Choose on-bits
        # Add the same readout probes if each_probe_1_on_bit is True
        if each_probe_1_on_bit:
            probe_on_bits = [np.random.choice(on_bits)] * N_readout_per_probe
        # Randomly choose readout probes without replacement if there are more possible probes than N_readout_per_probe
        elif len(on_bits) >= N_readout_per_probe:
            probe_on_bits = np.random.choice(on_bits, N_readout_per_probe, replace=False)
        # Randomly choose readout probes with replacement
        else:
            probe_on_bits = np.random.choice(on_bits, N_readout_per_probe, replace=True)

        probe_barcodes.append(on_bits_to_barcodes(probe_on_bits, len(barcode)))
        
        # Add the readout sequence to the left or right
        seq = row['target_sequence']
        ro_names = ''

        # Make n_left not random
        n_left = np.floor(N_readout_per_probe / 2)

        for j, ob in enumerate(probe_on_bits):

            ro_name = on_bit_dict[ob][0]
            ro_seq = on_bit_dict[ob][1]
            if j < n_left:
                ro_names = ro_name + ':' + ro_names 
                seq = ro_seq + spacer + seq
            else:
                ro_names = ro_names + ':' + ro_name 
                seq = seq + spacer + ro_seq
       
        readout_probe_names.append(ro_names)
        sequences.append(seq)
    
    probe_table['readout_names'] = pd.Series(readout_probe_names, index=probe_table.index)
    probe_table['probe_barcode'] = pd.Series(probe_barcodes, index=probe_table.index)
    probe_table['target_readout_sequence'] = pd.Series(sequences, index=probe_table.index)
    print(f'Added readout sequences to {probe_table.shape[0]} probes.')
    
    return probe_table

def add_readout_seqs_to_probes_random(probe_dict:dict, readout_seqs:pd.core.frame.DataFrame,
                                     barcode_table:pd.core.frame.DataFrame,
                                     N_readout_per_probe:int, spacer:str='',
                                     gene_id_key='name', n_threads=1,
                                     each_probe_1_on_bit:bool=False):
    '''Add readout sequences to probes by randomly choose on-bits.
    Arguments:
        probe_dict: The probe dictionary. The dataframes must have the "target_sequence" column.
        readout_seqs: The data frame of readout sequences with their on-bit positions.
        barcode_table: The barcode table of genes.
        N_readout_per_probe: Number of readout sequences to be added to each probe.
        spacer: The sequence to be added between readout sequences and target sequences.
        gene_id_key: The column name in the barcode table to specify genes. Should be "name" or "id".
        each_probe_1_on_bit: Force each probe to have only one on-bit.
    '''
    # Iterate through all genes and get the arguments for parallel processing
    ks = []
    args = []
    
    for gk in probe_dict.keys():
        # Get the barcode of the gene
        barcode = barcode_table[barcode_table[gene_id_key] == gk].iloc[0]['barcode_str']
    
        # Add readout sequences for all its transcripts
        for tk in probe_dict[gk].keys():
            ks.append((gk, tk))
            args.append([probe_dict[gk][tk], readout_seqs, barcode, N_readout_per_probe, spacer, each_probe_1_on_bit])
   
    # Add readout probes in parallel
    with Pool(n_threads) as p:
        results = p.starmap(add_readout_seqs_to_probes_of_transcript_random, args)
    
    # Update the probe dictionary
    for i, kk in enumerate(ks):
        gk, tk = kk
        probe_dict[gk][tk] = results[i]

