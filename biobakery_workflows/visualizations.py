"""
bioBakery Workflows: visualizations module
A collection of utilities for the document visualizations

Copyright (c) 2017 Harvard School of Public Health

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
"""

import os
import copy
import sys
import subprocess
import tempfile
import shutil

from . import utilities

def plot_hallagram(document, feature_set_1_data, feature_set_2_data, axis1_label, axis2_label, model=None, title=None,
    output_folder=None, strongest=10, show_table=False,q_value=0.1):
    """ Run halla on the two feature sets and plot the hallagram with the strongest associations 
        The first data line for each feature set should be a header of sample ids
        Requires halla v0.8.7
        If show_table is set, then instead of including heatmap include a table of associations
    """

    from matplotlib._png import read_png
    import matplotlib.pyplot as pyplot

    # create a temp output folder, if not provided
    if output_folder:
        outfolder = output_folder
        # if folder does not exist, then create
        if not os.path.isdir(outfolder):
            os.makedirs(outfolder)
    else:
        outfolder=tempfile.mkdtemp(suffix="biobakery_workflows_halla",dir=output_folder)

    # write the lines for the two feature set files
    feature_set_1 = os.path.join(outfolder,"feature1.tsv")
    feature_set_2 = os.path.join(outfolder,"feature2.tsv")
    for lines, file_name in [[feature_set_1_data,feature_set_1],[feature_set_2_data,feature_set_2]]:
        with open(file_name,"w") as file_handle:
            file_handle.write("\n".join(["\t".join(map(str,l)) for l in lines]))

    # run halla
    halla_command = ["halla","-X", feature_set_1, "-Y", feature_set_2,"--output", outfolder, "--header"]
    if model:
        halla_command += ["-m",model]
    try:
        subprocess.check_call(halla_command)
    except subprocess.CalledProcessError:
        print("Error: Unable to run halla")
    
    if show_table:
        # display the table of associations instead of including the heatmap
        associations_file = os.path.join(outfolder,"associations.txt")
        # check that the file is not empty
        with open(associations_file) as file_handle:
            associations_total = len(file_handle.readlines())-1

        if associations_total > 0:
            columns, row_names, halla_data = document.read_table(associations_file, format_data=str)

            # reduce data to only those columns to display in the table
            cluster_results = [[row[0].replace(";","\n"),row[2].replace(";","\n"),"{0:.7f}".format(float(row[4])),"{0:.3f}".format(float(row[5]))] for row in halla_data]
            # filter any results that are more than the max q_value
            cluster_results = list(filter(lambda row: float(row[-1]) < q_value, cluster_results))
        
            row_labels = list(map(lambda x: str(x)+"   ",range(1,len(cluster_results)+1)))
            column_labels = [axis1_label, axis2_label,"  p-value  ","q-value"]
            document.show_table(cluster_results, row_labels, column_labels, title, font=6)
        else:
            print("No associations found for "+title)
    else:
        # run hallagram
        output_png = os.path.join(outfolder,"hallagram.png")
        hallagram_command = ["hallagram",os.path.join(outfolder,"similarity_table.txt"),
            os.path.join(outfolder,"hypotheses_tree.txt"), os.path.join(outfolder,"associations.txt"),
            "--outfile",output_png,"--strongest",str(strongest),"--axlabels",axis1_label,axis2_label]
        if model:
            hallagram_command += ["--similarity",model]
        try:
            subprocess.check_call(hallagram_command)
        except subprocess.CalledProcessError:
            print("Error: Unable to run hallagram")

        if os.path.isfile(output_png):
            hallagram_png=read_png(output_png)        

            # create a subplot and remove the frame and axis labels
            fig = pyplot.figure()
            subplot = fig.add_subplot(111, frame_on=False)
            subplot.xaxis.set_visible(False)
            subplot.yaxis.set_visible(False)
        
            # set title if provided
            if title:
                fig.suptitle(title, fontsize=16)

            # show but do not interpolate (as this will make the text hard to read)
            try:
                pyplot.imshow(hallagram_png, interpolation="none")
            except TypeError:
                print("Unable to display hallagram plot")
                pass

            # this is needed to increase the image size (to fit in the increased figure)
            pyplot.tight_layout()

    # remove the temp folder
    if not output_folder:
        shutil.rmtree(outfolder) 

def plot_pcoa_top_average_abundance(document, samples, feature_names, feature_data, feature_type, scale_data=None, legend_title="% Abundance", max_sets=6):
    """ Plot multiple pcoa in a single figure for the top abundances for the feature set """

    # if function is provided, scale the abundance data
    if scale_data:
        new_data = []
        for row in feature_data:
            new_data.append(map(scale_data,row))
        feature_data = new_data

    # get the top features by average abundance
    top_names, top_data = utilities.top_rows(feature_names, feature_data, max_sets, function="average")

    top_abundances=dict((x,y) for x,y in zip(["#"+str(i+1)+" "+x for i,x in enumerate(top_names[:max_sets])], top_data[:max_sets]))
    document.show_pcoa_multiple_plots(samples, feature_names, feature_data,
        "PCoA Ordination of "+feature_type+", top "+str(max_sets)+" "+feature_type+" by average abundance", top_abundances, legend_title)
    
def qc_read_counts(document, file):
    """ Read in the file of read counts compiled from kneaddata logs with the utility script """
    
    columns, samples, data = document.read_table(file, format_data=int)
    
    # shorten known database names
    columns=[name.replace("SILVA_128_LSUParc_SSUParc_ribosomal_RNA","rRNA") for name in columns]
    columns=[name.replace("Homo_sapiens","hg38") for name in columns]
    columns=[name.replace("human_hg38_refMrna","mRNA") for name in columns]
    
    # change the names of the raw and trimmed columns (to include case)
    columns=[name.replace("raw","Raw").replace("trimmed","Trim").replace("decontaminated","") for name in columns]
    
    # check if this is single or paired end data
    if list(filter(lambda x: "single" in x, columns)):
        # remove single from the column name
        columns=[name.replace("single","").strip() for name in columns[:-1]]
        
        # return all but the final filtered column as this is not needed
        data=[row[:-1] for row in data]
        
    else:
        # remove the final columns from the list as these are not needed
        columns=list(filter(lambda x: not "final" in x, columns))
        
        # organize the data into pairs and orphans
        pairs_index = [index for index, name in enumerate(columns) if "pair1" in name]
        pairs_columns = [name.replace("pair1","").strip() for index, name in enumerate(columns) if index in pairs_index]
        orphans_index = [index for index, name in enumerate(columns) if "orphan" in name]
        orphans_columns = [name for index, name in enumerate(columns) if index in orphans_index]
        
        pairs_data=[]
        orphans_data=[]
        for row in data:
            pairs_data.append([])
            orphans_data.append([])
            for index in range(len(row)):
                if index in pairs_index:
                    pairs_data[-1].append(row[index])
                if index in orphans_index:
                    orphans_data[-1].append(row[index])
                
        columns = pairs_columns, orphans_columns
        data = pairs_data, orphans_data
    
    return columns, samples, data
    

def feature_counts(document, read_counts_file, feature_counts_file):
    """ Compute feature counts from the humann2 log read counts file and the feature counts file """
    
    # read in the read count and feature count files
    read_type, read_samples, read_count_data = document.read_table(read_counts_file)
    feature_type, feature_samples, feature_count_data = document.read_table(feature_counts_file)
    
    # remove any samples for which the prescreen did not find any species so nucleotide search was bypassed
    # these samples will have NA read counts but could have non-zero species count (species is the last column)
    read_samples, read_count_data = utilities.filter_zero_rows(read_samples, read_count_data, ignore_index=-1)
    
    # get the total reads for samples along with those for nucleotide alignment and translated
    # convert values to log10

    total_reads=[utilities.try_log10(row[read_type.index("total reads")]) for row in read_count_data]
    nucleotide_reads=[utilities.try_log10(row[read_type.index("total nucleotide aligned")]) for row in read_count_data]
    translated_reads=[utilities.try_log10(row[read_type.index("total translated aligned")]) for row in read_count_data]
    
    # sort the feature counts so they are in the same sample order as the read counts
    all_feature_counts={sample:row for sample, row in zip(feature_samples, feature_count_data)}
    sorted_feature_count_data=[all_feature_counts[sample] for sample in read_samples]
    
    # get the counts by each feature type
    # convert values to log10
    genefamilies_counts=[utilities.try_log10(row[feature_type.index("humann2_genefamilies_relab_counts")]) for row in sorted_feature_count_data]
    ecs_counts=[utilities.try_log10(row[feature_type.index("humann2_ecs_relab_counts")]) for row in sorted_feature_count_data]
    pathabundance_counts=[utilities.try_log10(row[feature_type.index("humann2_pathabundance_relab_counts")]) for row in sorted_feature_count_data]
    
    return total_reads, nucleotide_reads, translated_reads, genefamilies_counts, ecs_counts, pathabundance_counts

def write_pathway_average_variance_table(document, file_name, data, names_and_descriptions, format_table_decimal="{:.3}"):
    """ Write a file of the pathways including averages and variance """

    # get the average abundances and descriptions for the pathways
    top_average_pathways_file = os.path.join(document.data_folder, file_name)
    
    # get the average abundances, formatting as a single value per row 
    average_abundance_variance=[]
    for average, variance in zip(utilities.row_average(data), utilities.row_variance(data)):
        average_abundance_variance.append([format_table_decimal.format(average),format_table_decimal.format(variance)])
    
    document.write_table(["# Pathway","Average abundance", "Variance"], names_and_descriptions, 
                         average_abundance_variance, top_average_pathways_file)
    
    return average_abundance_variance

def top_average_pathways(document, file, max_sets):
    """ Read the pathways file and get the top average pathways """
    
    # read in the samples and get the data with out the stratification by bug
    samples, pathways, data = document.read_table(file)
    pathway_names = utilities.pathway_names(pathways)
    pathways, data = utilities.remove_stratified_pathways(pathways, 
        data, remove_description=True)
    
    # remove extra identifier from sample name if included in workflow
    samples = [sample.replace("_Abundance","") for sample in samples]
    
    # get the average abundance for the pathways
    top_pathways, top_data = utilities.top_rows(pathways,
        data, max_sets, function="average")
    
    # get the top names with descriptions
    top_names_and_descriptions = [name+":"+pathway_names[name] for name in top_pathways]
    
    return samples, top_pathways, top_data, top_names_and_descriptions

def show_table_max_rows(document, data, row_labels, column_labels, title, table_file,
    max_rows=20, format_data_comma=None, location="center", font=None, max_columns=7):
    """ For large numbers of samples, only show a reduced table """
    
    table_message="A data file exists of this table: "
    large_table_message="The table is too large to include the full table in this document."+\
        " A partial table is shown which includes only {max} {item}."+\
        " Please see the data file for the full table: "
        
    # check if there are too many rows
    partial_table_rows=False
    if len(row_labels) > max_rows:
        data=data[:max_rows]
        row_labels=row_labels[:max_rows]
        partial_table_rows=True
        
    # check if there are too many columns
    partial_table_columns=False
    if len(column_labels) > max_columns-1:
        data=[row[:max_columns-1] for row in data]
        column_labels=column_labels[:max_columns-1]
        partial_table_columns=True
        
    # determine the message and title if this is a full or partial table
    if partial_table_rows or partial_table_columns:
        if partial_table_rows:
            message=large_table_message.format(max=max_rows,item="rows")
        else:
            message=large_table_message.format(max=max_columns,item="columns")
        title+=" (partial table)"
    else:
        message=table_message
        
    # render the table
    document.show_table(data, row_labels, column_labels, 
        title, format_data_comma=format_data_comma, location=location, font=font)
    
    message+="[{file}](data/{file})".format(file=os.path.basename(table_file))
        
    return message

def print_pathways_urls(names, descriptions, total):
    """ List pathways with urls, including descriptions """
    
    print("Detailed functions of the top {} pathways can be found on the following MetaCyc pages:  ".format(total))
    
    print("")
    for pathway, desc in zip(names[:total], descriptions[:total]):
        print(" * ["+desc+"]("+utilities.metacyc_url(pathway)+")  ")
        
    print("")
    print("To learn more about other pathways, search for the pathway by name on the [MetaCyc](https://metacyc.org/) website.")

class Workflow(object):
    
    @classmethod
    def format_caption(cls,name,**keywords):
        return cls.captions[name].format(**keywords)

class ShotGun(Workflow):
    captions={}
    
    # add captions for functional data section
    captions["functional_intro"]="This report section contains preliminary "+\
        "exploratory figures that summarize HUMAnN2 functional profiling of "+\
        "all samples. HUMAnN2 performs species-specific and species-agnostic "+\
        " quantification of gene families, EC enzyme modules, and pathways, "+\
        "using the UniRef and MetaCyc databases. For more information on "+\
        "functional profiling and the databases used, see websites for "+\
        "[HUMAnN2](http://huttenhower.sph.harvard.edu/humann2), "+\
        "[UniRef](http://www.uniprot.org/help/uniref), "+\
        "and [MetaCyc](https://metacyc.org/)."
        
    captions["pathway_abundance_intro"]="Hierarchical clustering of samples "+\
        "and pathways, using top {max_sets} pathways "+\
        "with highest mean relative abundance among samples. "+\
        "The 'average linkage' clustering on the Euclidean "+\
        "distance metric was used to cluster samples. The pathway "+\
        "dendrogram is based on pairwise (Spearman) correlation between pathways."+\
        "Samples are columns and pathway are rows. The heatmaps were generated "+\
        "with [Hclust2](https://bitbucket.org/nsegata/hclust2)."
        
    captions["feature_detection"]="Feature detection as a function of sequencing "+\
        "depth. Effect of sample sequencing depth on the ability to detect "+\
        "microbiome functional features in {seq_type} sequence data. HUMAnN2 "+\
        "functional profiling of {seq_short_type} quality filtered reads was performed on "+\
        "individual samples in species-specific mode (blue), i.e. nucleotide "+\
        "alignment against pangenomes of species identified in the sample "+\
        "with MetaPhlAn2, and in combined species-specific and -agnostic "+\
        "(orange) mode, in which reads not matching any pangenome reference "+\
        "sequences were subjected to translated searching against the "+\
        "UniRef90 database. Each profiled sample is represented by a "+\
        "orange and blue point in each plot. Linear regression fit is "+\
        "represented by straight lines in each plot."
        
    captions["pathway_abundance_heatmap"]="Abundances were {norm} transformed "+\
        "prior to clustering. The color bar represents relative abundances on a {norm} scale."  
        
    captions["scatter_reads_aligned"]="Number of aligned reads in species-specific "+\
        "(nucleotide search) and species-agnostic (translated search) HUMAnN2 mode "+\
        "as a function of input reads."
        
    captions["scatter_features"]="Detection of UniRef90 gene families, enzyme modules,"+\
        " and pathways as a function of aligned reads."
        
    captions["microbial_ratios"]="Proportion of reads remaining after removing host"+\
        " reads relative to the number of: i) quality-trimmed reads, and ii) raw "+\
        "unfiltered reads."
        
    captions["qc_intro"]="This report section contains information about the "+\
        "quality control processing for all {total_samples} {seq_type} fastq input "+\
        "files. These files were run through the "+\
        "[KneadData](http://huttenhower.sph.harvard.edu/kneaddata) QC pipeline. "+\
        "Reads were first trimmed then filtered against contaminate reference database{dbs}. "
    
    captions["qc_intro_multiple_db"]="Reads were filtered sequentially "+\
        "with those reads passing the first filtering step used as input to the next "+\
        "filtering step. This chain of filtering removes reads from all references in serial."
        
    captions["qc_intro_paired"]="\n \nData is organized by paired "+\
        "and orphan reads. When one read in a pair passes a filtering step and "+\
        "the other does not the surviving read is an orphan."
        
    captions["qc_intro_table"]="\nThe tables and plots are annotated as follows:\n \n"+\
        " * raw : Untouched fastq reads.\n"+\
        " * trim : Number of reads remaining after trimming bases with Phred score < 20. If the "+\
        "trimmed reads is < 50% of original length then it is removed altogether.\n"
        
    # set descriptions for command qc databases
    captions["qc_databases"]={}
    captions["qc_databases"]["hg38"]="The human genome database is used to remove "+\
        "reads originating from the host DNA."
    captions["qc_databases"]["mRNA"]="The human transcriptome (hg38 mRNA) database "+\
        "is used to remove reads originating from host gene isoforms."
    captions["qc_databases"]["rRNA"]="The SILVA (rRNA) database is used to remove "+\
        " small and large subunit ribosomal RNA."
    
    @classmethod
    def print_qc_intro_caption(cls, total_samples, databases, paired=None):
        """ Generate the qc intro caption based on the samples and databases """
        
        caption=cls.captions["qc_intro"]
        
        # if there are multiple databases, add the description about sequential filtering
        if len(databases) > 1:
            caption+=cls.captions["qc_intro_multiple_db"]
        
        if paired:
            caption+=cls.captions["qc_intro_paired"]
        caption+=cls.captions["qc_intro_table"]
        
        # add each database to the list
        dbs_list=[]
        for db in databases:
            dbs_list.append(db)
            desc=cls.captions["qc_databases"].get(db,"")
            caption+=" * {db} : Number of reads after depleting against reference database {list}. {desc}\n".format(
                db=db,list=" and ".join(dbs_list), desc=desc)
        caption+=" \n"
        
        # get the sequence type string
        seq_type="single-end"
        if paired:
            seq_type="paired-end"
        
        # format the caption to include the specific details for this data set
        caption=caption.format(total_samples=total_samples, seq_type=seq_type,
            dbs="s: "+", ".join(databases[:-1])+" and "+databases[-1] if len(databases) > 1 else " "+databases[0])
        
        for line in caption.split("\n"):
            print(line)
        

class Sixteen_S(Workflow):
    captions={}
            
    captions["dada2intro"]="Implementing DADA2 pipeline for resolving sequence variants from 16S rRNA \
        gene amplicon paired-end sequencing reads,adopting the tutorial from\n\n \
         https://benjjneb.github.io/dada2/tutorial.html and \
        \n https://benjjneb.github.io/dada2/bigdata_paired.html \n\n with minor adjustments.\
        \n\nThis report captures all the workflow steps necessary to reproduce the analysis.\
        \nMultiple sequence alignment of resolved sequence variants is used to generate a phylogenetic tree,\
        which is required for calculating UniFrac beta-diversity distances between microbiome samples.\n"
    
    captions["dada2errorintro"]="The DADA2 algorithm depends on a parametric error model (err) and every amplicon dataset has a different set of error rates. \
        \nThe learnErrors method learns the error model from the data, by alternating estimation of the error rates and inference of \
        sample composition until they converge on a jointly consistent solution.\n\nAs in many optimization problems, the algorithm must \
        begin with an initial guess, for which the maximum possible error rates in this data are used \
        the error rates if only the most abundant sequence is correct and all the rest are errors).\n"
    
    captions["dada2errorinfo"]="The error rates for each possible transition (eg. A->T,A->G, etc) are shown. \
        Points are the observed error rates for each consensus quality score. \
        \nThe black line shows the estimated error rates after convergence. \
        \nThe red line shows the error rates expected under the nominal definition of the Q-value. \
        \n\nIf the black line (the estimated rates) fits the observed rates well, \
        and the error rates drop with increased quality as expected, then everything looks reasonable \
        and can proceed with confidence.\n"

    captions["dada2stepsinfo"]="\nDereplication combines all identical sequencing reads into into unique sequences with a corresponding abundance:\
        the number of reads with that unique sequence. DADA2 retains a summary of the quality information associated with each unique sequence.\
        \nThe consensus quality profile of a unique sequence is the average of the positional qualities from the dereplicated reads.\
        \n\nThese quality profiles inform the error model of the subsequent denoising step, significantly increasing DADA2's accuracy. \
        \n\nThe sample inference step performs the core sequence-variant inference algorithm to the dereplicated data. \
        Spurious sequence variants are further reduced by merging overlapping reads. \nThe core function here is mergePairs \
        which depends on the forward and reverse re.samples being in matching order at the time they were dereplicated \
        \n\nThe core dada method removes substitution and indel errors, but chimeras remain.\
        Fortunately, the accuracy of the sequences after denoising makes identifying chimeras simpler than it is when dealing with fuzzy OTUs\
        all sequences which can be exactly reconstructed as a bimera (two-parent chimera) from more abundant sequence." \
         + "\n\nIMPORTANT: Most of reads should remain after chimera removal (it is not uncommon for a majority of sequence variants to be removed though).\
        If most of your reads were removed as chimeric, upstream processing may need to be revisited.\
        In almost all cases this is caused by primer sequences with ambiguous nucleotides that were not removed prior to beginning the DADA2 pipeline.\n"  
    
    captions["dada2countsinfo"]="This figure shows the number of reads that made it through each step in the pipeline\
        \n\nOutside of filtering (depending on how stringent it is) there should no step in which a majority of reads are lost.\
        \n\nIf a majority of reads failed to merge, you may need to revisit the  truncLen parameter used in the filtering step\
        and make sure that the truncated reads span your amplicon.\
        \n\nIf a majority of reads failed to pass the chimera check, you may need to revisit the removal of primers,\
        as the ambiguous nucleotides in unremoved primers interfere with chimera identification.\n"   

    captions["dada2taxinfo"]="The assignTaxonomy function takes a set of sequences and a training set of taxonomically classified sequences,\
        and outputs the taxonomic assignments with at least minBoot bootstrap confidence.\
        \n\nFormatted training datasets for taxonomic assignments can be downloaded from here\
        https://benjjneb.github.io/dada2/training.html.\
        \n\n assignTaxonomy(... ) implements the RDP naive Bayesian classifier method described in Wang et al. 2007"  \
        + "\nIn short, the kmer profile of the sequences to be classified are compared against the kmer profiles of all sequences in a training set\
        of sequences with assigned taxonomies. The reference sequence with the most similar profile is used to assign taxonomy to the query sequence,\
        and then a bootstrapping approach is used to assess the confidence assignment at each taxonomic level.\n"
 
          
    captions["usearchcountsinfo"]="This figure shows counts of reads in three categories: \n\n1) classified: reads that align to OTUs with known taxonomy,\
        \n2) reads that align to OTUs of unknown taxonomy, \n3) reads that do not align to any OTUs. The sum of these\
        three read counts for each sample is the total original read count not including filtering prior to OTU clustering.\n"
     