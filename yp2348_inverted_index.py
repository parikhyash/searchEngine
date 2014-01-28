#!/usr/bin/python

import os
import anydbm
import re
import time
import sys
import cPickle as pickle
import xml.etree.ElementTree as ET
from porter import stem


docID={}	#stores mapping of document names to their IDs
inv_index={}	#hastable to store inverted index of the corpus
id_no=0 	#equivalent to static variable to store document IDs

#list of stopwords which are not supposed to be indexed
STOPWORDS = ['a','able','about','across','after','all','almost','also','am','among',
             'an','and','any','are','as','at','be','because','been','but','by','can',
             'cannot','could','dear','did','do','does','either','else','ever','every',
             'for','from','get','got','had','has','have','he','her','hers','him','his',
             'how','however','i','if','in','into','is','it','its','just','least','let',
             'like','likely','may','me','might','most','must','my','neither','no','nor',
           	 'not','of','off','often','on','only','or','other','our','own','rather','s','said',
             'say','says','she','should','since','so','some','than','that','the','their',
             'them','then','there','these','they','this','tis','to','too','twas','us',
             'wants','was','we','were','what','when','where','which','while','who',
             'whom','why','will','with','would','yet','you','your']

#parse the corpus document by docuemnt and process each document
def parse_corpus(path):
	global docID
	command = 'ls '+path	#ls the directory to get all the files for parsing
	files = os.popen(command).readlines()
	for single_file in files:	#iterate over each single file
		filename = single_file.rstrip('\n')
		build_docID(filename)	#map document name to document ID
		filepath = path+filename
		build_invIndex(id_no, filepath)	#add words in the file to the inverted index
	index_name = dumpIndex(path)
	index_size = os.path.getsize(index_name)
	print "Total number of words indexed:", len(inv_index)-1
	print "Size of the inverted index:", index_size, "bytes"
	print "Number of documents indexed:", len(docID)
	dumpDocID()

	
#mapping of doc names to doc IDs
def build_docID(filename):
	global docID
	global id_no
	id_no+=1
	docID[id_no]=filename

#XML parsing for the corpus documents
def parseXML(filepath):
	file_data=""
	tree = ET.parse(filepath)
	for node in tree.getiterator():
		if(node.tag=='TITLE' or node.tag=='AUTHOR' or node.tag=='TEXT' ):	#consider data from these tags
			file_data+=node.text
	return file_data	#returns all data from the file corpus as a string


#Build the entire inverted index document by document
#The inverted index has the word as the key and a list of documents and positions of the word as values
def build_invIndex(id, filepath):
	global inv_index
	current_file=open(filepath,'r')
	# file_data=current_file.read()	#read entire file into a string (Cranfield corpus has small files)
	file_data = parseXML(filepath)
	words = tokenize(file_data)	#returns tokens of the file
	position = 0
	wordcheck={}	#used to check if the word has already occurred in the saem file
	for word in words:
		position+=1
		if word in STOPWORDS:		#ignore stopwords
			continue
		if word not in inv_index:	#word encountered first time in the entire corpus
			inv_index[word]=[[id, [position-1]]]
			wordcheck[word]=1
		elif word in inv_index and word in wordcheck:	#word encountered again in the same file
			if wordcheck[word] == 1:
				inv_index[word][-1][1].append(position-1)
		elif word in inv_index and word not in wordcheck:	#word encountered again in the corpus, but not file
				inv_index[word].append([id, [position-1]])
				wordcheck[word]=1
	current_file.close()

#dump the index into a pickle file
def dumpIndex(path):
	index_name = "inverted_index.p"
	pickle.dump(inv_index, open(index_name, "wb" ))
	return index_name

#dump the document name to IDs mapping into a pickle file
def dumpDocID():
	pickle.dump(docID, open( "doc_id.p", "wb" ))


#processes the file and returns tokens
def tokenize(file_data):
	file_data=file_data.lower()	#lowercasing
	file_data = re.sub('[^0-9a-zA-Z]+', ' ', file_data)	#ignoring punctuations
	file_data = re.sub('(\w)\'(\w)/$1~$2', ' ', file_data)	#ignoring punctuations
	file_data = re.sub('\'/ ', ' ', file_data)	#ignoring punctuations

	file_words = file_data.split()	#split the file into single words

	count = 0
	for word in file_words:
		file_words[count] = stem(stem(word))
		count+=1
	return file_words


def main():
	global inv_index
	start = time.time()
	path=sys.argv[1]	#path to the corpus passed a coomand line argument
	# path = '../Cranfield_Collection/cranfieldDocs/'
	inv_index['cranfield_corpus_path']=path
	parse_corpus(path)
	end = time.time()
	print "Time to build the inverted index:", str(end - start), "seconds"


main()