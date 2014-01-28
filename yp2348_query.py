#!/usr/bin/python

import os
import anydbm
import re
import time
import sys
import shlex
import cPickle as pickle
import xml.etree.ElementTree as ET
from porter import stem

docID={}	#stores mapping of document names to their IDs
inv_index={}	#hashtable to store inverted index of the corpus
query_result={}	#stores the result of the query for further processing
path=''	#path to corpus
docList=[]	#list of documents that satisfy the query
df={}	#stores document frequency
negList=[]	#list of documents satisfying negation queries
tf={}	#stores term frequency
allDocs=[]	#list of alldocs in the corpus used as universal set
rank={}	#stores the rank of relevant documents (doc_no -> rank_score)
phrase_pos={}	#stores phrase positions for displaying snippets
phraseList=[]	#list od documents containing phrases
snippetDone=[]	#stores those documents whose snippets have been printed


#list of stopwords which are not supposed to be considered
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

#form list of all documents. Used as a Universal Set for set operations later on
def makeAllDocList():
	global allDocs
	global docID
	count=0
	for key in docID.keys():
		allDocs.append(key)
		count+=1

#process special queries
def specialQuery(query_words):
	global path
	global docID
	global rank

	#process special query to calculate term frequency of a word
	if query_words[0] == 'tf':
		doc_number=query_words[1]
		word=query_words[2] 
		if ' ' in word:
			processPhrase(word, "false")	#processphrase forms the rank table from which tf is extracted
			if int(doc_number) in rank:
				print rank[int(doc_number)]//len(word.split())
			else:
				print 0
		else:	
			postings = inv_index[word]	#tf for simple queries comes directly from postings list
			for doc in postings:
				if str(doc[0]) == str(doc_number):
					print len(doc[1])	#tf is the length of positions list for that word in the document
					return
			print 0
		return

	#process special query to find doc freqeuency
	if query_words[0] == 'df':
		word=query_words[1] 
		if ' ' in word:
			docs = processPhrase(word, "false")	#build the rank table by processing the phrase
			print len(docs)	#number of keys in the rank table = number of unique docs
		else:	
			if word in inv_index:
				print (len(inv_index[word]))  #for simple queries, simply count number of postings for that word
			else:
				print 0
		return

	#process special query to find frequency in the entire index
	if query_words[0] == 'freq':
		word=query_words[1] 
		# print rank
		if ' ' in word:
			processPhrase(word, "false")	#build the rank table by processing the phrase
			freq=0
			for document in rank:	#sum the score of all documents
				freq+=rank[document]
			print freq//len(word.split())	#divide by length since phrases get score equivalent to their length
		else:
			postings = inv_index[word]
			freq=0
			for doc in postings:	#count all positions across all documents for that word
				freq+=len(doc[1])
			print freq
		return 

	if query_words[0] == 'doc':
		tag = 'TEXT'
		if int(query_words[1])> len(docID):
			print "No such document!!"
			return
		filename=docID[int(query_words[1])]
		print returnXMLTag(filename, tag)	#use XML 'TEXT' tag to get the text of the document
		return

	if query_words[0] == 'titl':
		tag = 'TITLE'
		if int(query_words[1])> len(docID):
			print "No such document!!"
			return
		filename=docID[int(query_words[1])]
		print returnXMLTag(filename, tag)	#use XML 'TITLE' tag to get the title of the document
		return

	if query_words[0] == 'author':
		tag = 'AUTHOR'
		if int(query_words[1])> len(docID):
			print "No such document!!"
			return
		filename=docID[int(query_words[1])]
		print returnXMLTag(filename, tag)	##use XML 'AUTHOR' tag to get the author of the document
		return

#special queries for title and doc
def returnXMLTag(filename, tag):
	global path
	filepath=path+filename
	file_data=""
	tree = ET.parse(filepath)
	for node in tree.getiterator():	#retireve the text, title or doc for special queries
		if(node.tag==tag):
			file_data+=node.text
	return file_data

#list storing documents which are relevant to positive queries
def docListing(word, postings):
	global docList
	global rank
	for docs in postings:	#form a list of docs that contain single word queries without negation
		docList.append(docs[0])
		if docs[0] not in rank:
			rank[docs[0]]=len(docs[1])
		else: 
			rank[docs[0]]+=len(docs[1])

#list storing documents which are relevant to negative queries
def negativeListing(word, postings):
	global negList
	global allDocs
	global rank
	for docs in postings:	#form a list of docs that contain words of simple negation queries
		negList.append(docs[0])
	if len(negList) != 0:
		#take set difference with universal set to get documents not containg the query
		negList = difference(allDocs,negList)	
		for doc in negList:
			if doc in rank:
				rank[doc]+=1
			else:
				rank[doc]=1

#calculate tf
def calcTf(word, postings):	
	global tf
	global inv_index
	for docs in postings:
		if word not in tf:
			tf[word]=[[docs[0], len(docs[1])]]
		else:
			tf[word]=tf[word].append([docs[0], len(docs[1])])

#calculating df
def calcDf():
	if word in inv_index:
		return len(inv_index[word])
	else:
		return 0

#function to print the snippet of relevant documents
def getSnippet(filename, position):
	words = getDocWords(filename)
	#the conditions below handle words occuring at the very start or end of documents
	#under normal conditions, it will print two words before and after the query word
	if len(words)<5:
		print filename, "\t...", words[0], "..."
		return
	if (position+3)>len(words):
		print filename, "\t...", words[position-2], words[position-1], words[position], "..."
		return
	if (position-3)<0:
		print filename, "\t...", words[position], words[position+1], words[position+2], "..."
		return
	print filename, "\t...", words[position-2], words[position-1], words[position], words[position+1], words[position+2], "..."

#get the data in the document as a string
def getDocWords(filename):
	global path
	current_doc=open(path+filename, 'r')
	filepath=path+filename
	file_data = parseXML(filepath)
	file_data = re.sub('[^0-9a-zA-Z]+', ' ', file_data)	#ignoring punctuations
	file_data = re.sub('(\w)\'(\w)/$1~$2', ' ', file_data)	#ignoring punctuations
	file_data = re.sub('\'/ ', ' ', file_data)	#ignoring punctuations
	words = file_data.split()
	return words

#special function to process phrases
def processPhrase(query, negFlag):
	# global docList
	global docID
	global inv_index
	global rank
	global STOPWORDS
	global phrase_pos
	word_docs={}
	phrase_words=query.split()	#split the phrase into single words
	deletionList=[]
	for find_stop in phrase_words:	#remove stopwords from the phrase
		if find_stop in STOPWORDS:
			deletionList.append(find_stop)
	for find_stop in deletionList:
		phrase_words.remove(find_stop)
	count=0
	for word in phrase_words:
		phrase_words[count]=stem(stem(word))
		count+=1
	phrase_length=len(phrase_words)
	for word in phrase_words:
		word=stem(stem(word))
		if word not in inv_index:
			return []
		if word in inv_index:
			for docs in inv_index[word]:
				if word not in word_docs:
					word_docs[word]=[docs[0]]
				else:
					word_docs[word].append(docs[0])

	combinedList=[]	#stores documents in which all words of the phrase are present
	actualList=[]	#stores documents in which all words are present at adjacent positions
	count=0
	for docs in word_docs.values():	#forming the combined list
		if count == 0:
			combinedList=docs
		else:
			combinedList=list(set(combinedList) & set(docs))
		count+=1

	for doc in combinedList:	#processing docs in the combined list for adjacent positions of words
		phrase_count=0
		filename=docID[doc]
		words=getDocWords(filename)
		word=phrase_words[0]
		postings=inv_index[word]
		for entry in postings:	#takes a word in the phrase and checks for adajacent words in the document
			if entry[0] != doc:
				continue
			phrase_start=0
			for position in entry[1]:
				check="true"
				for i in range(0,phrase_length):	#iterates over phrase length to check adjacent positions
					if position+i<len(words):
						if stem(stem(words[position+i])) != phrase_words[i]:
							check="false"
							break
						elif position+i<len(words) and stem(stem(words[position+i])) == phrase_words[i]:
							continue
					else:
						check="false"
				if check == "true":
					if doc not in actualList:
						actualList.append(doc)
					phrase_start=position
					phrase_count+=1
		if phrase_count != 0:	#negation flag is to handle negation of phrases
			if negFlag == "false":
				if not doc in phrase_pos:	#rank documents other than the phrase for negation queries
					phrase_pos[doc]=phrase_start #position of the phrase for snippets
				if doc not in rank:
					rank[doc]=phrase_count*len(phrase_words)
				else:
					rank[doc]+=(phrase_count*len(phrase_words))
		# if phrase_count==0:
		# 	combinedList.remove(doc)
	#the result is the intersection of the real list and combined list
	combinedList=intersect(actualList,combinedList)	
	return combinedList

#XML parsing for a document for special queries like 'title 1'
def parseXML(filepath):
	file_data=""
	tree = ET.parse(filepath)
	for node in tree.getiterator():
		if(node.tag=='TITLE' or node.tag=='AUTHOR' or node.tag=='TEXT' ):
			file_data+=node.text
	return file_data

#logic to calculate and display snippets
def displaySnippets(resultSet, query_words):
	global rank
	global inv_index
	global allDocs
	global phrase_pos
	global phraseList
	global snippetDone
	#sort the result set according to ranking
	resultSet = sorted(resultSet, key=lambda k: rank[k],reverse=True)
	for doc in resultSet:
		flag="false"
		printNegation="false"
		for word in query_words:
			#simple query => print directly from position in posting list
			if "!" not in word and " " not in word:	
				postingList = inv_index[word]
				for postings in postingList:
					if postings[0]==doc:
						flag="true"
						printNegation="false"
						if doc not in snippetDone:
							getSnippet(docID[doc],postings[1][0])
							snippetDone.append(doc)
						break
			#phrase query => print from phrase_pos
			elif " " in word and "!" not in word:
				if doc in phraseList:
					if doc not in snippetDone:
						getSnippet(docID[doc], phrase_pos[doc])
						snippetDone.append(doc)
			#negation of a phrase => print start of the document as snippet
			elif " " in word and "!" in word:
				if doc not in snippetDone:
					getSnippet(docID[doc], 2)
					snippetDone.append(doc)
			#negation query => print start of the document if no other word in query has the document
			elif "!" in word:
				word=word[1:]
				postingList = inv_index[word]
				list1=[]
				for postings in postingList:
					list1.append(postings[0])
				list1 = difference(allDocs,list1)
				for d in list1:
					if d==doc:
						printNegation="true"
						break
			if flag=="true":
				break
		if printNegation=="true":
			if doc not in snippetDone:
				getSnippet(docID[doc],2)
				snippetDone.append(doc)
	# print "Number of results:", len(resultSet)
	# print resultSet

#load the inverted index from the pickle file
def loadIndex():
	global inv_index
	inv_index = pickle.load(open("inverted_index.p", "rb"))

#load the id->document mapping from the pickle file
def loadDocID():
	global docID
	docID = pickle.load(open("doc_id.p", "rb"))

#takes union of positive query docs
def posUnion():
	global docList
	combinedList=[]
	combinedList=list(set(combinedList) | set(docList))
	return combinedList

#takes union of negative query docs
def negUnion():
	global negList
	combinedList=[]
	combinedList=list(set(combinedList) | set(negList))
	return combinedList

#set difference
def difference(a, b):
    return list(set(a) - set(b))

#set intersection
def intersect(a, b):
    return list(set(a) & set(b))

#set union
def union(a, b):
    return list(set(a) | set(b))

#EXTERNAL MODULE - calculate edit distance used in similarity
def levenshtein(a,b):
    n, m = len(a), len(b)
    if n > m:
        a,b = b,a
        n,m = m,n
        
    current = range(n+1)
    for i in range(1,m+1):
        previous, current = current, [i]+[0]*n
        for j in range(1,n+1):
            add, delete = previous[j]+1, current[j-1]+1
            change = previous[j-1]
            if a[j-1] != b[i-1]:
                change = change + 1
            current[j] = min(add, delete, change)
            
    return current[n]

def main():
	global docID
	global inv_index
	global path
	global phraseList
	global query_result
	global docList
	global negList
	global tf
	global df
	global allDocs
	global rank
	global phrase_pos
	global phraseList
	global snippetDone
	while(True):
		loadIndex()
		path = inv_index['cranfield_corpus_path']
		loadDocID()
		query=raw_input("\nEnter your query or a special command (tf/df/freq/title/doc/author/similar) (Enter goodbye to exit)\n")
		start = time.time()
		makeAllDocList()
		#convert entire query to lower case
		query = query.lower()
		if query == 'goodbye':
			print "Thank you for using this information retrieval system.."
			break
		#shlex is used to split pharses and words separately
		query_words=shlex.split(query)
		count = 0
		#stemming of the query
		for word in query_words:
			if " " not in word:
				query_words[count] = stem(stem(word))
			count+=1
		phraseList=[]
		negPhraseList=[]
		#process special query 'similar'
		if query_words[0] == 'similar':
			flag="false"
			for word in inv_index.keys():
				dist = levenshtein(query_words[1],word)
				if dist==1:
					flag="true"
					print word
			if flag == "false":
				print "No similar words found"
			query_result={}	#stores the result of the query for further processing
			docList=[]
			df={}	
			negList=[]	
			tf={}	
			allDocs=[]	
			rank={}	
			phrase_pos={}	
			phraseList=[]	
			snippetDone=[]
			continue
		#process special query tf/df/freq/doc/title/author
		if query_words[0] == 'tf' or query_words[0] == 'df' or query_words[0] == 'freq' or query_words[0] == 'doc' or query_words[0] == 'titl' or query_words[0] == 'author':
			negFlag="false"
			specialQuery(query_words)
			query_result={}	#stores the result of the query for further processing
			docList=[]
			df={}	
			negList=[]	
			tf={}	
			allDocs=[]	
			rank={}	
			phrase_pos={}	
			phraseList=[]	
			snippetDone=[]
			continue
		#process each word in the query
		for word in query_words:
			#single word
			if word in inv_index and word[0] != '!':
				postings=inv_index[word]
				docListing(word, postings)
			#single word with negation
			elif word[0]=='!' and word[1:] in inv_index and " " not in word:
				postings=inv_index[word[1:]]
				negativeListing(word[1:], postings)
			#phrase with negation
			elif " " in word and word[0]=='!':
				negPhraseList=negPhraseList+processPhrase(word[1:], "true")
			#phrase without negation
			elif " " in word:
				phraseList=phraseList+processPhrase(word, "false")
		#take set difference with universal set for phrase negation
		if len(negPhraseList) != 0:
			negPhraseList=difference(allDocs,negPhraseList)
			for doc in negPhraseList:
				if doc not in rank:
					rank[doc]=1
				else: 
					rank[doc]+=1
		#set operations on results
		docSet=posUnion() # Set A
		docSet=list(set(docSet) | set(phraseList)) # A = A U B
		negSet=negUnion()	#Set C
		negSet=list(set(negSet) | set(negPhraseList))	#C = C U D
		resultSet=union(docSet,negSet)	# RESULT = A U C = (A U B) U (C U D)
		#Display snippets if results have been found
		if len(resultSet)!=0:
			displaySnippets(resultSet, query_words)
		else:
			print "No match found!"
		print "Number of results:", len(resultSet)
		# print resultSet
		end = time.time()
		print "\nTook", (end-start), "seconds to give the results"

		#Re-initilaize global variables for the next query 
		query_result={}	#stores the result of the query for further processing
		docList=[]
		df={}	
		negList=[]	
		tf={}	
		allDocs=[]	
		rank={}	
		phrase_pos={}	
		phraseList=[]	
		snippetDone=[]

main()