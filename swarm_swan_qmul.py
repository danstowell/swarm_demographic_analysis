
import numpy as np
import csv, os
from copy import deepcopy

import matplotlib
#matplotlib.use('PDF') # http://www.astrobetter.com/plotting-to-a-file-in-python/
import matplotlib.pyplot as plt
import matplotlib.cm as cm
from matplotlib.backends.backend_pdf import PdfPages
plt.rcParams.update({'font.size': 6})

import seaborn as sns 	# https://seaborn.pydata.org/generated/seaborn.violinplot.html
import pandas as pd

#########################################################################################
# user config

datasrcs = {
'2017-2018':'data/workloads_1718_2018-11-12.csv',
'2018-2019':'data/workloads_1819_2018-11-12.csv',
}

##########################################
# you probably don't need to change these:


fieldnamemapper = {
	'User.gender': 'gender',
	'User.givenName': 'givenname',
	'JOB_FAMILY': 'contracttype'
}

fieldvalumapper = {
	'Teaching & Research': 'T&R',
	'Research': 'R',
	'Teaching and Scholarship': 'T&S',
}

fields_to_skip = ['ID', 'JGF_ID', 'User._rootId', 'User.personNumber', 'ModuleWorkload.data_rsas_notes', 'User.email', 'GROUP', 'groupHeirarchy.0', 'groupHeirarchy.1', 'groupHeirarchy.2', 'groupHeirarchy.3', 'groupHeirarchy.4', 'groupHeirarchy.5']

#########################################################################################
# Loading the data

def fieldparser(k, v, fieldnamemapper_extended):
	k = fieldnamemapper_extended.get(k, k)
	v = fieldvalumapper.get(v, v)
	if k in ['givenname', 'gender', 'contracttype']:
		pass  # string is fine
	else:
		if v=='':
			v = None
		else:
			v = float(v)
	return k,v

def rowparser(row, workloadcats, genderlookup, fieldnamemapper_extended):
	"Convert a CSV row from SWARM into typed data fields. NB it may manipulate the passed-in workloadcats array."
	row = dict(fieldparser(k,v, fieldnamemapper_extended) for k,v in row.items() if k not in fields_to_skip)
	row['gender'] = genderlookup.get(row['givenname'], '')
	if len(workloadcats)==0:
		# here, having hit the first row, we calculate the workload cats
		new_workloadcats = [k for k in row.keys() if k.startswith("MODULE_WORKLOAD_") or k.startswith("ModuleWorkload.data_") or k.startswith("workload_")]
		# we also have to expand the fieldmappings, and then re-convert the keynames explicitly
		for acat in new_workloadcats:
			shortercat = acat.replace("MODULE_WORKLOAD_", "").replace("ModuleWorkload.data_", "").replace("workload_", "").lower()
			fieldnamemapper_extended[acat] = shortercat
		new_workloadcats = [fieldnamemapper_extended.get(k, k) for k in new_workloadcats]
		row          = {fieldnamemapper_extended.get(k, k):v for k,v in row.items()}
		workloadcats.extend(sorted(new_workloadcats))
		#print("Workload categories: %s" % workloadcats)
		#print("Fields: %s" % row.keys())
	return row

#########################################################################################

def load_and_preprocess(datasrc, genderlookup):
	"give a CSV path. returns a dict with the 'data' and the other aux data structures"

	fieldnamemapper_extended = deepcopy(fieldnamemapper)

	# load the data
	workloadcats = []  # this gets populated when the first row to be loaded is encountered
	with open(datasrc, 'r') as infp:
		rdr = csv.DictReader(infp, delimiter='\t')
		data = [rowparser(row, workloadcats, genderlookup, fieldnamemapper_extended) for row in rdr]

	# drop those with as-yet-unidentified gender
	unrecordedgender = [row['givenname'] for row in data if row['gender']=='']
	count = len(unrecordedgender)
	if count:
		print("WARNING: %i entries have missing data for gender - will remove them from the analysis: %s" % (count, unrecordedgender))
		data = [row for row in data if row['gender']!='']

	print("Loaded %i rows." % len(data))

	# get lookup list of gender, jobtype
	# also, drop singleton columns? (NB also remove them from the workloadcats)
	valsused = {k:list(set([row[k] for row in data])) for k in data[0].keys()}
	singletons = []
	for k, vallist in valsused.items():
		if len(vallist) < 2:
			print("WARNING: column %s is a singleton - will remove it from the data" % k)
			singletons.append(k)
	# remove singletons
	workloadcats = [acat for acat in workloadcats if acat not in singletons]
	data = [{k:v for k,v in row.items() if k not in singletons} for row in data]

	##################################################################
	# transform itemised workloads into proportion-of-target-workloads
	def proportionalise_row(row):
		row = deepcopy(row)
		for acat in workloadcats:
			if acat=='target': continue
			row[acat] = 100 * row[acat] / row['target']
		return row

	count = len([row for row in data if row['target']==0])
	if count:
		print("WARNING: %i entries have zero target-workload - will remove them from the proportional analysis" % count)
	dataprop = [proportionalise_row(row) for row in data if row['target']!=0]
	#for row in dataprop:
	#	print row

	#######
	# finally, for easy plotting, convert to pandas dataframes
	data     = pd.DataFrame(data={k:[row[k] for row in data    ] for k in     data[0].keys()})
	dataprop = pd.DataFrame(data={k:[row[k] for row in dataprop] for k in dataprop[0].keys()})

	return {
		'raw': data,
		'prop': dataprop,
		'workloadcats': workloadcats,
		'valsused': valsused,
	}


#########################################################################################
if __name__ == '__main__':

	with open('data/genderlookup.csv', 'r') as infp:
		rdr = csv.DictReader(infp, delimiter='\t')
		genderlookup = {row['givenname']:row['gender'] for row in rdr}

	data = {k:load_and_preprocess(datasrc, genderlookup) for k,datasrc in datasrcs.items()}
	years = sorted(data.keys())

	print data['2018-2019']['raw'][data['2018-2019']['raw']['givenname']=='Dan Stowell']  # for example

	#for row in data['prop']:
	#	print row
	
	#######################################################
	# Analyses

	pdf = PdfPages('plot_swarm_swan_qmul.pdf')
	sns.set(style="whitegrid")

	plt.figure()
	plt.text(0.5, 0.5, "QMUL EECS Athena Swan team\nSWARM overview\n\n(DRAFT - data is incomplete and not finalised)")
	plt.gca().axis('off')
	pdf.savefig(bbox_inches='tight')
	plt.close()


	# simple stats:
	# gender vs jobtype (subtotals... as a simple bar chart?)
	fig, axes = plt.subplots(1, len(data), figsize=(12,8))
	for whichyear, yearlbl in enumerate(years):

		groupedcounts = data[yearlbl]["raw"].groupby(["gender", "contracttype"]).count()["givenname"].to_frame().reset_index()

		ax = sns.barplot(x="contracttype", hue="gender", y="givenname", data=groupedcounts, ax=axes[whichyear])
		ax.set_ylim(ymax=100)
		if whichyear!=0:
			ax.set(ylabel='')
		else:
			ax.set(ylabel='# people')
		ax.set_title(yearlbl)

	pdf.savefig()
	plt.close()


	# gender & jobtype vs targetworkload, and vs totalworkload
	fig, axes = plt.subplots(2, len(data), figsize=(12,8))
	for whichyear, yearlbl in enumerate(years):

		ax = sns.swarmplot(x="contracttype", hue="gender", y="target", data=data[yearlbl]['raw'],
					dodge=True, ax=axes[0,whichyear])
		ax.set_title(yearlbl)
		ax.set_ylim(ymin=0, ymax=2500)
		ax.set(xlabel='')
		if whichyear!=0:
			ax.set(ylabel='')

		ax = sns.swarmplot(x="contracttype", hue="gender", y="total", data=data[yearlbl]['raw'],
					dodge=True, ax=axes[1,whichyear])
		ax.set_ylim(ymin=0, ymax=2500)
		if whichyear!=0:
			ax.set(ylabel='')

	pdf.savefig()
	plt.close()


	# violin plots of each workload type's proportion

	# NB we need to harmonise the cats across years...
	allworkloadcats = []
	for somedata in data.values():
		allworkloadcats.extend(somedata['workloadcats'])
	allworkloadcats = sorted(list(set(allworkloadcats)))

	for workloadcat in allworkloadcats:
		if workloadcat in ['total', 'target']:
			continue
		fig, axes = plt.subplots(1, len(data), figsize=(12,8))
		for whichyear, yearlbl in enumerate(years):

			if workloadcat in data[yearlbl]['workloadcats']:

				ax = sns.swarmplot(x="contracttype", hue="gender", y=workloadcat, data=data[yearlbl]['prop'],
							dodge=True, ax=axes[whichyear])
				ax.set_title(yearlbl)
				ax.set_ylim(ymin=0, ymax=100)
				if whichyear!=0:
					ax.set(ylabel='')
				else:
					ax.set(ylabel='%s (%% of target total workload)' % workloadcat)
			else:
				axes[whichyear].remove()

		pdf.savefig()
		plt.close()

	pdf.close()

