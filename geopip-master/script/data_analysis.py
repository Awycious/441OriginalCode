#!/usr/bin/python

# System modulas.
import sys
import os
import json
from copy import deepcopy
from time import time

# Get directories.
dir_script = os.getcwd()
dir_main = dir_script[:dir_script.rfind('/')]
dir_source = dir_main + '/src'
dir_data = dir_main + '/data'
# Add source path into import path.
sys.path.append(dir_source)

# Estimation functions.
from pip_est import *
from ctmc_est import *
from geopip_est import *
from geopip_sim import *

# Utility functions.
from substitution_util import *
from tree_util import *
from align_util import *

# I/O functions.
from io_json import *
from io_files import *
from io_fasta import *
from io_phylip import *
from io_phyml import *
from io_util import *


# Result folder directory.
resultFolder = dir_main + '/result/data_analysis'
if not os.path.exists(resultFolder):
    os.makedirs(resultFolder)
os.chdir(resultFolder)
# Substitution model directory.
modelDirectory = dir_main + '/model/gtr-model'
# Result folders for estimating rate matrix using Java code.
eStepFile, parametersPath, inputLoc, outputLoc, dataLoc = make_global_location_files(resultFolder, 'runs')
javaDirectory = dir_main + '/software/java'
# Result folder for dumping Java outputs.
execsLoc = resultFolder + '/state/execs'
if not os.path.exists(execsLoc):
    os.makedirs(execsLoc)
# Exact result folder for every run.
subFolderPath = resultFolder + '/runs'
if not os.path.exists(subFolderPath):
    os.makedirs(subFolderPath)
rFileLoc = dir_source

# Alphabet of characters considered, fixed for DNA.
cList = ['A', 'C', 'G', 'T']
# Indel only alphabet.
cListOne = ['?']
nList = len(cList)

###############################################################################
# Get the input file in .fasta format.
fastaFile = dir_data + '/molluscan.fasta'

# Read fasta.
multiAlign = read_fasta(fastaFile)
# Change RNA data to DNA data if needed.
multiAlign = multi_align_rna_to_dna(multiAlign)
# Change all characters to upper case.
multiAlign = multi_align_upper_case_only(multiAlign)
# Remove empty MSA columns.
multiAlign = multi_align_remove_all_empty_sites(multiAlign, step=1)
# Remove MSA columns with unknown characters.
multiAlign = multi_align_remove_unknown_sites(multiAlign, cList)
# Change special characters in sequence name to symbol '.'.
multiAlign = multi_align_revise_keys(multiAlign)

# Output cleaned data in fasta and phylip format.
dict_write_fasta(multiAlign, dataLoc)
dict_write_phylip(multiAlign, dataLoc)
# Output substitution only data.
dict_write_phylip_subs_only(multiAlign, dataLoc)
# Output indel only data.
multiAlignOne = ctmc0_multi_align(multiAlign, cList, missingSym='?')
dict_write_fasta(multiAlignOne, dataLoc, 'msaOne.fasta')

###############################################################################
# Start the inference steps.
# Update Q or not.
updateQ = True

# phyml
phymlLoc = dir_main + '/software/phyml'

time1 = time()
phyml_run(dataLoc, phymlLoc, fileName='msa.phylip.txt')
time1 = time() - time1

qMatPhyml = get_qmat_from_phyml_output(dataLoc)
alpha = get_alpha_from_phyml_output(dataLoc)

# common start values
qMatStart = qMatPhyml
nStartValue = 1

# CTMC only with one sub rate
qMatCTMC1, bDictCTMC1, treeCTMC1, nllkCTMC1 = opt_ctmc_full(qMatStart, multiAlign, javaDirectory, modelDirectory, eStepFile, parametersPath, inputLoc, outputLoc, dataLoc, execsLoc, rFileLoc, cList, qRates=[1.], suffix='_ctmc_1rate', updateQ=updateQ, tol=1.e-2, bTol=1.e-4, iterMax=100)

write_dist_from_bdict(bDictCTMC1, dataLoc, suffix='_ctmc_1rate')
output_qmat(qMatCTMC1, dataLoc, suffix='_ctmc_1rate')

# Calcuate 4 discrete Gamma rates.
qRates = mean_values(4, alpha)

# CTMC only with 4 sub rates
qMatCTMC4, bDictCTMC4, treeCTMC4, nllkCTMC4 = opt_ctmc_full(qMatStart, multiAlign, javaDirectory, modelDirectory, eStepFile, parametersPath, inputLoc, outputLoc, dataLoc, execsLoc, rFileLoc, cList, qRates=qRates, suffix='_ctmc_4rate', updateQ=updateQ, tol=1.e-2, bTol=1.e-4, iterMax=100)

# Output results.
write_dist_from_bdict(bDictCTMC4, dataLoc, suffix='_ctmc_4rate')
output_qmat(qMatCTMC4, dataLoc, suffix='_ctmc_4rate')

# PIP.
rateStart = pip_start_data(multiAlign)

time2 = time()
rateEstPIP, qMatEstPIP, bDictEstPIP, treeEstPIP = opt_pip_full(rateStart, qMatStart, multiAlign, javaDirectory, modelDirectory, eStepFile, parametersPath, inputLoc, outputLoc, dataLoc, execsLoc, rFileLoc, cList, qRates=[1.], suffix='_pip', updateQ=updateQ)
time2 = time() - time2

# Output results.
write_dist_from_bdict(bDictEstPIP, dataLoc, suffix='_pip')
output_qmat(qMatEstPIP, dataLoc, suffix='_pip')
output_ratelist(rateEstPIP, dataLoc, suffix='_pip')

# PIP no substitutions.
pairsList = bDictEstPIP.keys()

pairAlignOne = pair_align_from_multi_align(multiAlignOne)
segRateDictPIP = {0: rateEstPIP[0]}
piProbEstPIP = pi_from_qmat(qMatEstPIP)

bDictEstPIPOne = opt_nlists_bonly(pairsList, pairAlignOne, segRateDictPIP, piProbEstPIP, qMatEstPIP, qRates=[1.], cList=cListOne)

# Output results.
outNameLoc, outDistLoc, outTreeLoc = get_out_name_dist_tree_files(dataLoc, suffix='_pip_no_sub')
rCodeNj = get_rscript(outNameLoc, outDistLoc, outTreeLoc, rFileLoc)
tree_use_r_for_unknown_number_of_leaves(bDictEstPIPOne, pairsList, rCodeNj, dataLoc, outTreeLoc, suffix='_pip_no_sub', rooted=True)

write_dist_from_bdict(bDictEstPIPOne, dataLoc, suffix='_pip_no_sub')

# GeoPIP.
m = 10
pStart = 0.01
iRateOverdRate = 5

piProbRatesStart = np.ones(m) / m
lenSegsStart = [len(multiAlign.values()[0])]

# Random starts.
ratesListStart = []
for i in xrange(m):
    dRate = rd.random() * 4
    iRate = dRate * iRateOverdRate
    ratesListStart.append((iRate, dRate))

dRateMean = sum(zip(*ratesListStart)[1]) / m
iRateMean = dRateMean * iRateOverdRate
segRateDictStart = {0: (iRateMean, dRateMean)}

geopipSuffix = '_geopip_'+str(m)

time3 = time()
bDictEst1, qMatEst1, segRateDictEst1, alignsInSegEst1, pEst1, piProbRatesEst1, ratesListEst1, lenSegsEst1, treeEst1, nllk1 = opt_geopip_full(m, pStart, qMatStart, segRateDictStart, piProbRatesStart, ratesListStart, multiAlign, lenSegsStart, javaDirectory, modelDirectory, eStepFile, parametersPath, inputLoc, outputLoc, dataLoc, execsLoc, rFileLoc, cList, suffix=geopipSuffix, updateQ=updateQ, updateSeg=True, updateRate=True, updateRateFixdRateTimesTau=True, tol=1.e-2, bTol=1.e-3, iterMax=100)
time3 = time() - time3

# Output results.
write_dist_from_bdict(bDictEst1, dataLoc, suffix=geopipSuffix)
output_qmat(qMatEst1, dataLoc, suffix=geopipSuffix)
output_lensegs(lenSegsEst1, dataLoc, suffix=geopipSuffix)
output_ratelist(ratesListEst1, dataLoc, suffix=geopipSuffix)

rateCatListEst1 = ratecatlist_from_segratedict_and_ratelist(segRateDictEst1, ratesListEst1)
output_ratecat(rateCatListEst1, dataLoc, suffix=geopipSuffix)
rateCatAtEachLoc = output_ratecatateachloc(segRateDictEst1, ratesListEst1, lenSegsEst1, dataLoc, suffix=geopipSuffix)

output_rate_with_msa(multiAlign, rateCatAtEachLoc, dataLoc + '/msa_rate.txt')

# GeoPIP no substitutions.
pairsList = bDictEst1.keys()

qMatEstGeoPIP = qMatEst1
piProbEstGeoPIP = pi_from_qmat(qMatEstGeoPIP)

pairAlignOne = pair_align_from_multi_align(multiAlignOne, lenSegsEst1)

bDictEstGeoPIPOne = opt_nlists_bonly(pairsList, pairAlignOne, segRateDictEst1, piProbEstGeoPIP, qMatEstGeoPIP, qRates=[1.], cList=cListOne)

geopipOneSuffix = geopipSuffix + '_no_sub'
outNameLoc, outDistLoc, outTreeLoc = get_out_name_dist_tree_files(dataLoc, suffix=geopipOneSuffix)
rCodeNj = get_rscript(outNameLoc, outDistLoc, outTreeLoc, rFileLoc)
tree_use_r_for_unknown_number_of_leaves(bDictEstGeoPIPOne, pairsList, rCodeNj, dataLoc, outTreeLoc, suffix=geopipOneSuffix, rooted=True)

write_dist_from_bdict(bDictEstGeoPIPOne, dataLoc, suffix=geopipOneSuffix)


###############################################################################
# Post-processing.
# All trees.
treeNames = ['ctmc_1rate', 'ctmc_4rate', 'phyml_1rate', 'phyml_4rate', 'pip', 'pip_no_sub', geopipSuffix[1:], geopipOneSuffix[1:]]
tns = dendropy.TaxonNamespace()

# Get all trees.
treeAllNonScaled = []
treeAllScaled = []
for treeName in treeNames:
    treeFile = dataLoc+'/tree_' + treeName + '.txt'
    treeTemp = dendropy.Tree.get_from_path(treeFile, schema='newick', taxon_namespace=tns)
    treeAllNonScaled.append(treeTemp)
    treeTemp = dendropy.Tree.get_from_path(treeFile, schema='newick', taxon_namespace=tns)
    treeTemp.scale_edges(1. / treeTemp.length())
    treeAllScaled.append(treeTemp)

# Output wRF among unscaled trees.
treeDictNonScaled = dict(zip(treeNames, treeAllNonScaled))
treeDistNonScaled = dist_among_trees(treeDictNonScaled)
outDistNonScaledFile = dataLoc + '/dist_trees_non_scaled.txt'
with open(outDistNonScaledFile, 'w') as f:
    json.dump(treeDistNonScaled, f, sort_keys=True, indent=4)

# Output wRF among scaled trees.
treeDictScaled = dict(zip(treeNames, treeAllScaled))
treeDistScaled = dist_among_trees(treeDictScaled)
outDistScaledFile = dataLoc + '/dist_trees_scaled.txt'
with open(outDistScaledFile, 'w') as f:
    json.dump(treeDistScaled, f, sort_keys=True, indent=4)

# Output RF among trees.
treeDistSym = dist_among_trees_sym(treeDictNonScaled)
outDistSymFile = dataLoc + '/dist_trees_sym.txt'
with open(outDistSymFile, 'w') as f:
    json.dump(treeDistSym, f, sort_keys=True, indent=4)


####################################################
# Output result summary into file print.txt.
outputFile = dataLoc + '/print.txt'
sys.stdout = open(outputFile, 'w')

print '### summary statistics ###'
print 'data from:', fastaFile
print 'number of sequences:', len(multiAlign)
print 'number of sites:', len(multiAlign.values()[0])
print 'iRate / dRate:', iRateOverdRate
print 'time (PhyML, PIP, GeoPIP):', time1, time2, time3

print 'alpha:', alpha
print 'qRates:', qRates

print '### Robinson Foulds difference among trees (not scaled) ###'
print json.dumps(treeDistNonScaled, sort_keys=True, indent=4)

print '### Robinson Foulds difference among trees (scaled) ###'
print json.dumps(treeDistScaled, sort_keys=True, indent=4)

print '### plot trees ###'
for treeName, treeOne in treeDictScaled.iteritems():
    print treeName
    print treeOne.print_plot()
