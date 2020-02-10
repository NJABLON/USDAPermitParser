#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Copyright Indigo Ag Inc., 2019
Created 2019

@author: njablonski@indigoag.com
USDAPermitPdfParser.py
Parses data from USDA permits and creates LIMS Permit upload files 

Usage:

Example:

"""

from tika import parser
import csv
import glob
import argparse
import re
import sys, os

def read_pdf(filename):	
	denied_start_index = 0
	permit_guidance_index = 0

	#raw = parser.from_file('P526P-18-04155 MO.pdf')
	raw = parser.from_file(filename)
	pdfstring = raw['content'].replace('\n\n', '\n').replace('\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n', '')

	pdfline = pdfstring.splitlines()    

	for line in pdfline:
		if 'PERMIT' in line.strip():
			permit_num_index = pdfline.index(line)
			if 'PERMIT NUMBER:' in line.strip() or 'PERMITNUMBER:' in line.strip():
				lineSplit = line.strip().split(' ')
				permitNumber = lineSplit[-1]
				if 'NUMBER:' in permitNumber:
					numLineSplit = permitNumber.split(':')
					permitNumber = numLineSplit[-1]
				continue
			# PERMIT & NUMBER on different lines
			elif 'NUMBER:' in pdfline[permit_num_index+1]:
				lineSplit = pdfline[permit_num_index+1].strip().split(' ')
				permitNumber = lineSplit[-1]
				continue
		if 'APPLICATION NUMBER:' in line.strip() or 'APPLICATIONNUMBER:' in line.strip():
			lineSplit = line.strip().split(' ')
			appNumber = lineSplit[-1]
			if 'NUMBER:' in appNumber:			
				appNumberSplit = appNumber.split(':')
				appNumber = appNumberSplit[-1]
				continue
		if 'DATE ISSUED:' in line.strip():
			lineSplit = line.strip().split(' ')
			dateIssued = lineSplit[-1]
			continue
		if 'EXPIRES:' in line.strip():
			lineSplit = line.strip().split(' ')
			expDate = lineSplit[-1]
			continue
		if 'DESTINATION:' in line.strip():
			lineSplit = line.strip().split(' ')
			state = lineSplit[-1]
			if len(state) > 2 and len(lineSplit) > 1:
				state = lineSplit[-2][-2:]
			continue
		if line.startswith('RELEASE:'):
			countiesFilled = False
			counter = 1
			release_line_index = pdfline.index(line)
			releaseSection = pdfline[release_line_index]

			# counties on separate lines
			while not countiesFilled:
				if not ')' in releaseSection:
					releaseSection += pdfline[release_line_index + counter]
					counter += 1
				else:
					countiesFilled = True
			releaseSection = releaseSection.replace('RELEASE:', '')
			county_start_index = releaseSection.find(':')
			county_stop_index = releaseSection.find(')')
			counties = releaseSection[county_start_index+2:county_stop_index].strip().replace(',', ';')		
		if 'Under the conditions specified, this permit authorizes the following:' in line:
			taxonomy_start_index = pdfline.index(line)
			continue
		if 'DENIED ORGANISM(S)' in line:
			denied_start_index = pdfline.index(line)
			continue
		# if PERMIT GUIDANCE missing from permit, use PERMIT CONDITIONS to signal end of taxonomy section
		if 'PERMIT GUIDANCE' in line:
			taxonomy_stop_index = pdfline.index(line)
			permit_guidance_index = taxonomy_stop_index
			continue
		if line =='PERMIT CONDITIONS' and permit_guidance_index == 0:
			taxonomy_stop_index = pdfline.index(line)
		#if 'USDA-APHIS issues' in line.strip():
		if line =='PERMIT CONDITIONS':
			conditions_start_index = pdfline.index(line) + 1
			continue		
		#if line[:3] == '1. ':
		if 'END OF PERMIT CONDITIONS' in line:
			conditions_stop_index = pdfline.index(line)
			continue		

	# Taxonomy section
	taxonomyData = pdfline[taxonomy_start_index:taxonomy_stop_index]
	genus = ''
	species = ''
	genusSpeciesApprovedList = []
	genusSpeciesDeniedList = []
	intendedUse = ''
	intendedUseCheck = ''
	intendedUseFilled = False
	genusSpeciesValid = False	

	for line in taxonomyData:

		# Intended Use on separate lines 
		res = [i for i in intended_use_list if line.replace("Any","").strip() in i]
		#if any(item in line for item in intended_use_list):
		#	intendedUse = item
		if len(res) > 0 and not intendedUseFilled:
			intendedUseCheck += line.replace("Any","").strip() + ' '
			if intendedUseCheck.strip() in intended_use_list:
				intendedUse = intendedUseCheck.strip()
				intendedUseFilled = True
		#Intended Use on same line w/ no space separating Shipment Origins data
		#res = [i for i in intended_use_list if i in line]

		lineSplit = line.strip().split(' ')
	    
		if lineSplit[0].replace("[","").replace("]","") in genus_list:
			genus = lineSplit[0].replace("[","").replace("]","")
			#Genus and species on same line
			if len(lineSplit) > 1:
				#No space between species and Life Stage(s) column
				#if there's an uppercase letter in lineSplit[1], need to remove the Life Stage data from species
				if not lineSplit[1].islower() and not re.search("[A-Z]",lineSplit[1]) == None:
					speciesCheck = lineSplit[1].replace("[","").replace("]","")
					speciesCheck = speciesCheck[:re.search("[A-Z]",speciesCheck).end()-1]
					if speciesCheck in species_list:
						species = speciesCheck
				else:
					if lineSplit[1].replace("[","").replace("]","") in species_list:
						species = lineSplit[1].replace("[","").replace("]","")
	        #Species on different line from genus
			else:
				continue
		if lineSplit[0].replace("[","").replace("]","") in species_list:
			species = lineSplit[0].replace("[","").replace("]","")					
	                
		# Species with no genus
		if genus != '' and species == '':
			genusIndex = genus_list.index(genus)
			speciesValidate = species_list[genusIndex]
			if speciesValidate == species:
				genusSpeciesValid = True
		
		if (genus != '' and species != '') or genusSpeciesValid:
			if pdfline.index(line) < denied_start_index or denied_start_index == 0:
				genusSpeciesApprovedList.append(genus + ' ' + species)
			else:
				genusSpeciesDeniedList.append(genus + ' ' + species)
		genus = ''
		species = ''
		genusSpeciesValid = False

	# for some reason reading line by line, a genus/species is read in twice even though it's not visibly in the file twice
	# remove duplicates from list to fix
	genusSpeciesApprovedList = list(set(genusSpeciesApprovedList))
	genusSpeciesApprovedList.sort()
	
	# need this format to have multiple associations in upload file
	genusSpeciesApproved = "\"," + ','.join(genusSpeciesApprovedList) + ",\""
	
	if len(genusSpeciesDeniedList) > 0:
		genusSpeciesDenied = "\"," + ','.join(genusSpeciesDeniedList) + ",\""
		genusSpeciesCombined = "\"," + ','.join(genusSpeciesApprovedList) + ',' + ','.join(genusSpeciesDeniedList) + ",\""
	else:
		genusSpeciesCombined = genusSpeciesApproved
		genusSpeciesDenied = ''

	print("Applied: " + genusSpeciesCombined)
	print("Approved: " + genusSpeciesApproved)  
	print("Denied: " + genusSpeciesDenied)          

	# Permit Conditions section
	permitConditions = pdfline[conditions_start_index:conditions_stop_index]
	myPermitConditions = ''
	authUsersList = []
	authCompanyList = []

	for line in permitConditions:
		if 'Permit Number' not in line and 'THIS PERMIT HAS BEEN APPROVED ELECTRONICALLY BY THE FOLLOWING' not in line\
		and 'PPQ HEADQUARTER OFFICIAL VIA EPERMITS' not in line and 'DATE' not in line and 'Carl Schulze' not in line and 'Carlos Blanco' not in line\
		and 'Osmond Baron' not in line and 'Vickie Brewster' not in line and 'WARNING: Any alteration' not in line and 'U.S.C.s 7734(b)' not in line and '$10,000,' not in line\
		and 'Page ' not in line and '* * * CBI Copy * * *' not in line and line[:6] != 'United' and line[:13] != 'Department of'\
		and line[:11] != 'Agriculture' and 'http' not in line:
			myPermitConditions += line + ' ' 

			# get authorized user and organization
			if intendedUse == 'Research - Field' and line.startswith('This permit authorizes') and not line.startswith('This permit authorizes the'):
				authFilled = False
				counter = 0
				auth_line_index = permitConditions.index(line)
				authSection = permitConditions[auth_line_index + counter]

				while not authFilled:
					counter += 1
					pcCheck = permitConditions[auth_line_index + counter]				
					if not pcCheck.startswith('1.') and not pcCheck.startswith('This permit authorizes'):						
						authSection += pcCheck						
					else:
						authFilled = True

				authSection = authSection.replace('This permit authorizes ', '').replace('; and ', ';')
				authSectionSplit = authSection.split(';')

				for auth in authSectionSplit:
					of_index = auth.find('of')
					comma_index = auth.find(',')
					commaIndexes = [pos for pos, char in enumerate(auth) if char == ',']
					# Auth User and Organization separated by commas
					if comma_index > 0 and of_index == -1:
						authUsersList.append(auth[0:comma_index].replace('[', '').replace(']', ''))
						authCompanyList.append(auth[comma_index+2:commaIndexes[1]].replace('[', '').replace(']', ''))
					else:
						authUsersList.append(auth[0:of_index-1].replace('[', '').replace(']', ''))
						authCompanyList.append(auth[of_index+2:comma_index].replace('[', '').replace(']', ''))
			

	authorizedUsers = '; '.join(authUsersList).strip().replace(',', ';')
	authorizedCompanies = '; '.join(authCompanyList).strip().replace(',', ';')
	myPermitConditions = myPermitConditions.replace("Animal and Plant Health Inspection Service","").replace("Plant Protection & Quarantine", "").strip()

	#only want authorization info for Field permits
	if intendedUse != 'Research - Field':
		authorizedUsers = ''
		authorizedCompanies = ''
		counties = ''

	dataList = ['PERMIT', '', permitNumber, appNumber, permitNumber, dateIssued, expDate, state, 'USA', myPermitConditions, intendedUse, authorizedUsers, authorizedCompanies, counties, genusSpeciesCombined, genusSpeciesApproved, genusSpeciesDenied]
	csvData.append(dataList)

def create_csv():
    
    with open(pathname + "\\permitUpload.csv", 'w', newline='') as csvfile:
        filewriter = csv.writer(csvfile)
        filewriter.writerows(csvData)
        
    csvfile.close()

def main():
	files = glob.glob(pathname + "\\*.pdf")
	print(files)

	for file in files:
	    print("Parsing: " + file)
	    read_pdf(file)
	    
	create_csv()   


if __name__ == '__main__':

	#parser = argparse.ArgumentParser()
	#parser.add_argument('-d', '--dir', help='Directory where files located', required=False)
	#args = parser.parse_args() ###
	#print(args.dir)

	#currentDirectory = os.getcwd()
	pathname = os.path.dirname(sys.argv[0])

	csvData = []
	csvData.append(['ENTITY TYPE', 'BARCODE', 'Name', 'ApplicationNumber', 'PermitNumber', 'IssueDate', 'ExpirationDate', 'State', 'Country', 'Conditions', 'IntendedUse', 'AuthorizedUsers', 'AuthorizedOrganizations', 'AuthorizedCounties', 'APPLIEDTAXONOMY', 'APPROVEDTAXONOMY', 'DENIEDTAXONOMY'])
	
	genus_list = ['Achlya','Achlya','Achroia','Achromobacter','Achromobacter','Achromobacter','Acidovorax','Acinetobacter','Acinetobacter','Acremonium','Acremonium','Acremonium','Acremonium','Acremonium','Acrosternum','Actinomucor','Aeromicrobium','Afipia','Agreia','Agrobacterium','Agrobacterium','Agrobacterium','Agrobacterium','Agromyces','Allophoma','Alpinaria','Altererythrobacter','Alternaria','Alternaria','Annulohypoxylon','Aphis','Aphis','Aplosporella','Arthrobacter','Arthrobacter','Arthrobacter','Ascochyta','Ascochyta','Ascochyta','Aspergillus','Aspergillus','Aspergillus','Aspergillus','Aspergillus','Aspergillus','Aspergillus','Aspergillus','Aspergillus','Aspergillus','Aspergillus','Aureimonas','Aureobasidium','Aureobasidium','Azorhizobium','Azorhizobium','Azospirillum','Bacillus','Bacillus','Bacillus','Bacillus','Bacillus','Bacillus','Bacillus','Bacillus','Bacillus','Bacillus','Bacillus','Bacillus','Bacillus','Bacillus','Bacillus','Bacillus','Bacillus','Bacillus','Bacillus','Bacillus','Bacillus','Bacteria','Bipolaris','Biscogniauxia','Blastoschizomyces','Bosea','Bosea','Brachybacterium','Bradyrhizobium','Bradyrhizobium','Bradyrhizobium','Bradyrhizobium','Bradyrhizobium','Brevibacillus','Brevibacillus','Brevibacillus','Brevibacillus','Brevibacillus','Brevundimonas','Brochothrix','Burkholderia','Burkholderia','Burkholderia','Burkholderia','Burkholderia','Burkholderia','Candida','Caulobacter','Caulobacteraceae','Cedecea','Cellulomonas','Cellulomonas','Cellulomonas','Cellulosimicrobium','Cercospora','Cercospora','Cercospora','Chaetomium','Chaetomium','Chaetomium','Chitinophaga','Chitinophaga','Chitinophaga','Chitinophaga','Chitinophaga','Chryseobacterium','Chryseobacterium','Chryseobacterium','Chryseobacterium','Chungangia','Citricoccus','Citrobacter','Cladosporium','Cladosporium','Cladosporium','Cladosporium','Cladosporium','Cladosporium','Clavibacter','Cochliobolus','Cochliobolus','Cochliobolus','Cochliobolus','Cohnella','Colaspis','Colletotrichum','Colletotrichum','Colletotrichum','Colletotrichum','Colletotrichum','Colletotrichum','Collimonas','Comamonas','Comamonas','Coniochaeta','Coniochaeta','Coniochaeta','Coniochaeta','Coniochaeta','Coniochaeta','Coniochaeta','Coniothyrium','Corynespora','Cryobacterium','Curlvularia','Curtobacterium','Curtobacterium','Curtobacterium','Curtobacterium','Curtobacterium','Curtobacterium','Curvularia','Curvularia','Curvularia','Curvularia','Dermacoccus','Devosia','Diabrotica','Diaporthe','Diaporthe','Didymella','Dietzia','Diplodia','Dyadobacter','Dyella','Edenia','Emericellopsis','Engyodontium','Enhydrobacter','Ensifer','Enterobacter','Enterobacter','Enterobacter','Enterobacter','Enterobacter','Enterobacter','Enterococcus','Epichloe','Epicoccum','Epicoccum','Erwinia','Erwinia','Escherichia','Euschistus','Exiguobacterium','Exophiala','Exophiala','Falsirhodobacter','Fictibacillus','Flavobacterium','Flavobacterium','Frigoribacterium','Fungi','Fusarium','Fusarium','Fusarium','Fusarium','Fusarium','Fusarium','Fusarium','Fusarium','Fusarium','Fusarium','Fusarium','Fusarium','Fusarium','Fusarium','Fusarium','Fusarium','Fusarium','Fusarium','Fusarium','Fusarium','Gaeumannomyces','Geodermatophilus','Geopyxis','Geotrichum','Gibellulopsis','Glomus','Gluconacetobacter','Gluconobacter','Gordonia','Hanseniaspora','Helicoverpa','Herbaspirillum','Herbiconiux','Heterodera','Janibacter','Janthinobacterium','Kaistia','Kineococcus','Kitasatospora','Klebsiella','Kocuria','Kocuria','Kosakonia','Kosakonia','Labedella','Labrys','Lachnoclostridium','Lactococcus','Leclercia','Leifsonia','Lelliottia','Lelliottia','Leptosphaerulina','Leucobacter','Luteibacter','Luteibacter','Luteibacter','Lygus','Lysinibacillus','Lysinibacillus','Lysinibacillus','Lysobacter','Magnaporthe','Magnaporthe','Massarina','Massilia','Massilia','Mayetiola','Meloidogyne','Meloidogyne','Mesorhizobium','Methylobacterium','Microbacterium','Microbacterium','Microbacterium','Micrococcus','Micrococcus','Micrococcus','Microsphaeropsis','Moraxella','Mucilaginibacter','Mucor','Mucor','Mucor','Mucor','Mucor','Mycetocola','Mycobacterium','Mycosphaerella','Neisseria','Neopestalotiopsis','Neorhizobium','Nezara','Nigrospora','Nocardia','Nocardioides','Nocardioides','Nocardioides','Novosphingobium','Ochrobactrum','Ochrobactrum','Paecilomyces','Paecilomyces','Paenibacillus','Paenibacillus','Paenibacillus','Paenibacillus','Paenibacillus','Paenibacillus','Paenibacillus','Paenibacillus','Paenisporosarcina','Pantoea','Pantoea','Pantoea','Pantoea','Pantoea','Pantoea','Pantoea','Pantoea','Paraboeremia','Paraburkholderia','Paracoccus','Paraconiothyrium','Paraconiothyrium','Paraphaeosphaeria','Pedobacter','Pedobacter','Pelomonas','Penicillium','Penicillium','Penicillium','Penicillium','Penicillium','Penicillium','Penicillium','Periconia','Periconia','Pestalotiopsis','Pestalotiopsis','Pestalotiopsis','Pestalotiopsis','Phaeosphaeria','Phaeosphaeria','Phakopsora','Phialemonium','Phomopsis','Phycicoccus','Phyllobacterium','Phytobacter','Phytophthora','Pithomyces','Plantibacter','Pratylenchus','Pratylenchus','Pratylenchus','Pratylenchus','Pratylenchus','Pratylenchus','Pratylenchus','Promicromonospora','Promicromonospora','Providencia','Pseudaminobacter','Pseudarthrobacter','Pseudeurotium','Pseudomonas','Pseudomonas','Pseudomonas','Pseudomonas','Pseudomonas','Pseudomonas','Pseudomonas','Pseudomonas','Pseudomonas','Pseudomonas','Pseudomonas','Pseudomonas','Pseudomonas','Pseudomonas','Pseudomonas','Pseudomonas','Pseudomonas','Pseudomonas','Pseudomonas','Pseudomonas','Pseudoxanthomonas','Psychrobacter','Puccinia','Puccinia','Pyrenophora','Pythium','Pythium','Pythium','Pythium','Pythium','Pythium','Pythium','Pythium','Pythium','Raoultella','Raoultella','Rathayibacter','Rhizobium','Rhizobium','Rhizobium','Rhizobium','Rhizoctonia','Rhodanobacter','Rhodococcus','Rhodoligotrophos','Rhopalosiphum','Rhopalosiphum','Rotylenchulus','Saccharibacillus','Sagenomella','Sanguibacter','Schizothecium','Sclerotinia','Sclerotium','Serratia','Setosphaeria','Setosphaeria','Shimazuella','Shinella','Siccibacter','Siphonobacter','Solibacillus','Sphaerulina','Sphingobacterium','Sphingobacterium','Sphingobium','Sphingobium','Sphingomonas','Sphingomonas','Sphingomonas','Sphingomonas','Sphingomonas','Sphingopyxis','Spodoptera','Sporosarcina','Stagonosporopsis','Staphylococcus','Stenocarpella','Stenotrophomonas','Stenotrophomonas','Stenotrophomonas','Stenotrophomonas','Stenotrophomonas','Stenotrophomonas','Stenotrophomonas','Streptococcus','Streptomyces','Streptomyces','Streptomyces','Streptomyces','Streptomyces','Streptomyces','Streptomyces','Streptomyces','Streptomyces','Streptomyces','Streptomyces','Streptomyces','Talaromyces','Talaromyces','Talaromyces','Talaromyces','Talaromyces','Terrabacter','Terrabacter','Terribacillus','Thermomonas','Tilletia','Tilletia','Tilletia','Trichoderma','Trichoderma','Trichoderma','Trichoderma','Trichoderma','Trichophaea','Ustilaginoidea','Variovorax','Variovorax','Variovorax','Verticillium','Vibrissea','Wheat','Williamsia','Xanthomonas','Xanthomonas']
	species_list = ['conspicua','klebsiana','grisella','insuavis','spp.','xylosoxidans','sp.','lwoffii','spp.','alternatum','kiliense','sp.','strictum','zeae','hilare','elegans','sp.','','sp.','larrymoorei','rhizogenes','sp.','tumefaciens','sp.','zantedeschiae','rhododendri','sp.','alternata','metachromatica','truncatum','glycines','gossypii','prunicola','sp','sp.','','medicaginicola','rabiei','viciae-pannonicae','flavus','fumisynnematus','hortai','hortai','lentulus','lentulus','pachycristatus','parasiticus','ruber','rugulosus','sydowii','sp.','iranianum','thailandense','caulinodans','sp.','brasilense','altitudinis','amyloliquefaciens','aryabhattai','butanolivorans','circulans','endophyticus','flexus','halotolerans','licheniformis','marisflavi','megaterium','methylotrophicus','mojavensis','pumilus','simplex','sp.','stratosphericus','subtilis','vallismortis','velezensis','','','saccharicola','cinereolilacina','spp.','ssp.','thiooxidans','sp.','diazoefficiens','elkanii','japonicum','sp.','spp.','agri','formosus','laterosporus','sp.','spp.','spp.','sp.','cenocepacia','contaminans','gladioli','glumae','phenazinium','sp.','','sp.','bacterium','spp.','humilata','sp.','','','gossypii','sojina','zeae-maydis','coarctatum','globosum','','ginsengisegetis','oryzae','sancti','sp.','','hominis','sp.','spp.','ssp.','sp.','sp.','spp.','cladosporioides','limoniforme','macrocarpum','minourae','oxysporum','tenuissimum','sp.','heterostrophus','miyabeanus','sativus','sp.','spp.','brunnea','coffeanum','dematium','gossypii','graminicola','helianthi','sp.','sp.','spp.','testosteroni','cateniformis','endophytica','ligniaria','nepalica','nivea','polymorpha','savoryi','prosopidis','cassiicola','sp.','protuberata','citreum','flaccumfaciens','oceanosedimentum','pusillum','sp.','','alcornii','protuberata','sp.','spicifera','sp.','sp.','virgifera','eres','helianthi','glomerata','sp.','medicaginis','sp.','sp.','gomezpompae','pallida','album','sp.','sp.','asburiae','cloacae','cowanii','sp.','spp.','','spp.','festucae','latusicollum','nigrum','persicina','spp.','','servus','','nigra','oligosperma','sp.','sp.','sp.','spp.','sp.','','acuminatum','armeniacum','avenaceum','cerealis','culmorum','equiseti','fujikuroi','graminearum','moniliforme','oxysporum','phaseoli','poae','pseudograminearum','solani','sporotrichioides','subglutinans','tricinctum','vasinfectum','verticillioides','virguliforme','graminis','spp.','majalis','','nigrescens','intraradices','liquefaciens','cerinus','','uvarum','zea','spp.','sp.','glycines','sp.','sp.','species','sp.','gansuensis','sp.','rhizophila','spp.','cowanii','sacchari','sp.','sp.','sp.','sp.','adecarboxylata','sp.','amnigena','zeae','australis','sp.','mycovicinus','rhizovicinus','sp.','lineolaris','sp.','sphaericus','','spp.','grisea','oryzae var. oryzae','igniaria','niastensis','spp.','destructor','arenaria','incognita','spp.','spp.','oxydans','sp.','testaceum','luteus','sp.','spp.','olivacea','','sp.','bainieri','brunneogriseus','circinelloides','fragilis','racemosus','sp.','','graminicola','','sp.','sp.','viridula','oryzae','spp.','sp.','sp.','spp.','sp.','anthropi','spp.','lilacinus','victoriae','amylolyticus','glycanilyticus','peoriae','polymyxa','sp.','spp.','taichungensis','terrigena','','agglomerans','ananatis','dispersa','endophytica','eucalypti','sp.','spp.','','camelliae','caledonica','sp.','brasiliense','sporulosum','sporulosa','spp.','terrae','spp.','chrysogenum','halotolerans','melanoconidium','minioluteum','mononematosum','oxalicum','viridicatum','byssoides','macrospinosa','endophytica','neglecta','rhododendri','versicolor','avenaria','nodorum','pachyrhizi','inflatum','chimonanthi','spp.','spp.','spp.','sojae','cynodontis','','alleni','brachyurus','hexincisus','neglectus','penetrans','scribneri','zeae','kroppenstedtii','spp.','spp.','spp.','sp.','bakeri','abietaniphila','arenae','chlororaphis','corrugata','fluorescens','frederiksbergensis','fulva','harudinis','hirundinis','marginalis','moraviensis','oleovorans','oryzihabitans','protegens','rhodesiae','soli','sp.','spp.','straminea','vranovensis','spp.','sp.','striiformis','triticina','tritici-repentis','aristosporum','debaryanum','echinulatum','helicoides','irregulare','oryzae','spinosum','ultimum','volutum','sp.','','sp.','pusense','sp.','spp.','tropici','solani','spp.','sp.','spp.','maidis','padi','reniformis','spp.','verticillata','sp.','inaequale','sclerotiorum','oryzae','sp.','monoceras','turcica','spp.','spp.','colletis','spp.','','oryzina','spp.','zeae','spp.','yanoikuyae','sanguinis','sp.','spp.','yanoikuyae','zeae','spp.','frugiperda','','cucurbitacearum','spp.','maydis','indicatrix','maltophilia','pavanii','rhizophila','sp.','spp.','zeae','spp.','badius','canus','ciscaucasicus','drozdowiczii','fulvissimus','kathirae','lydicus','parvus','rishiriensis','sp.','spp.','xanthochromogenes','flavus','macrosporus','pinophilus','subaurantiacus','veerkampii','spp.','','spp','spp.','horrida','indica','walkeri','afroharzianum','atroviride','harzianum','piluliferum','spirale','hemisphaerioides','virens','ginsengisoli','sp.','spp.','dahliae','truncorum','streak mosaic virus','sp.','campestris','sp.']
	intended_use_list = ['Research - Field', 'Seed treatment facility', 'Seeds to be treated at facility', 'Research - Greenhouse (growth chamber and lab included)', 'Research - Growth Chamber (lab included)']

	main()