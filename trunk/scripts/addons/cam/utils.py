# blender CAM utils.py (c) 2012 Vilem Novak
#
# ***** BEGIN GPL LICENSE BLOCK *****
#
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.	See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ***** END GPL LICENCE BLOCK *****

#here is the main functionality of Blender CAM. The functions here are called with operators defined in ops.py. All other libraries are called mostly from here.

import bpy
import time
import mathutils
import math
from math import *
from mathutils import *
from bpy.props import *
import bl_operators
from bpy.types import Menu, Operator
from bpy_extras import object_utils
import curve_simplify
import bmesh
import Polygon
#import Polygon.Utils as pUtils
import numpy
import random,sys, os
import pickle
import string
from cam import chunk
from cam.chunk import *
from cam import collision
from cam.collision import *
#import multiprocessing 
from cam import simple
from cam.simple import * 
from cam import pattern
from cam.pattern import *
from cam import polygon_utils_cam
from cam.polygon_utils_cam import *
from cam import image_utils
from cam.image_utils import *

try:
	from shapely.geometry import polygon as spolygon
	from shapely import ops as sops
	from shapely import geometry as sgeometry
	SHAPELY=True
except:
	SHAPELY=False
	
def positionObject(operation):
	ob=bpy.data.objects[operation.object_name]
	minx,miny,minz,maxx,maxy,maxz=getBoundsWorldspace([ob]) 
	ob.location.x-=minx
	ob.location.y-=miny
	ob.location.z-=maxz

def getBoundsWorldspace(obs):
	#progress('getting bounds of object(s)')
	t=time.time()
		
	maxx=maxy=maxz=-10000000
	minx=miny=minz=10000000
	for ob in obs:
		bb=ob.bound_box
		mw=ob.matrix_world
		if ob.type=='MESH':
			for c in ob.data.vertices:
				coord=c.co
				worldCoord = mw * Vector((coord[0], coord[1], coord[2]))
				minx=min(minx,worldCoord.x)
				miny=min(miny,worldCoord.y)
				minz=min(minz,worldCoord.z)
				maxx=max(maxx,worldCoord.x)
				maxy=max(maxy,worldCoord.y)
				maxz=max(maxz,worldCoord.z)
		else:
			
			for coord in bb:
				#this can work badly with some imported curves, don't know why...
				#worldCoord = mw * Vector((coord[0]/ob.scale.x, coord[1]/ob.scale.y, coord[2]/ob.scale.z))
				worldCoord =mw * Vector((coord[0], coord[1], coord[2]))
				minx=min(minx,worldCoord.x)
				miny=min(miny,worldCoord.y)
				minz=min(minz,worldCoord.z)
				maxx=max(maxx,worldCoord.x)
				maxy=max(maxy,worldCoord.y)
				maxz=max(maxz,worldCoord.z)
			
	#progress(time.time()-t)
	return minx,miny,minz,maxx,maxy,maxz

def getOperationSources(o):
	if o.geometry_source=='OBJECT':
		#bpy.ops.object.select_all(action='DESELECT')
		ob=bpy.data.objects[o.object_name]
		o.objects=[ob]
	elif o.geometry_source=='GROUP':
		group=bpy.data.groups[o.group_name]
		o.objects=group.objects
	elif o.geometry_source=='IMAGE':
		o.use_exact=False;
	
def getBounds(o):
	#print('kolikrat sem rpijde')
	if o.geometry_source=='OBJECT' or o.geometry_source=='GROUP':
		if o.material_from_model:
			minx,miny,minz,maxx,maxy,maxz=getBoundsWorldspace(o.objects)

			o.min.x=minx-o.material_radius_around_model
			o.min.y=miny-o.material_radius_around_model
			o.max.z=maxz
				
			if o.minz_from_ob:
					o.min.z=minz
					o.minz=o.min.z
			else:
				o.min.z=o.minz#max(bb[0][2]+l.z,o.minz)#
			
			o.max.x=maxx+o.material_radius_around_model
			o.max.y=maxy+o.material_radius_around_model
		else:
			o.min.x=o.material_origin.x
			o.min.y=o.material_origin.y
			o.min.z=o.material_origin.z-o.material_size.z
			o.max.x=o.min.x+o.material_size.x
			o.max.y=o.min.y+o.material_size.y
			o.max.z=o.material_origin.z
		
			
	else:
		i=bpy.data.images[o.source_image_name]
		if o.source_image_crop:
			sx=int(i.size[0]*o.source_image_crop_start_x/100)
			ex=int(i.size[0]*o.source_image_crop_end_x/100)
			sy=int(i.size[1]*o.source_image_crop_start_y/100)
			ey=int(i.size[1]*o.source_image_crop_end_y/100)
			#operation.image.resize(ex-sx,ey-sy)
			crop=(sx,sy,ex,ey)
		else:
			sx=0
			ex=i.size[0]
			sy=0
			ey=i.size[1]
			
		o.pixsize=o.source_image_size_x/i.size[0]
		
		o.min.x=o.source_image_offset.x+(sx)*o.pixsize
		o.max.x=o.source_image_offset.x+(ex)*o.pixsize
		o.min.y=o.source_image_offset.y+(sy)*o.pixsize
		o.max.y=o.source_image_offset.y+(ey)*o.pixsize
		o.min.z=o.source_image_offset.z+o.minz
		o.max.z=o.source_image_offset.z
	s=bpy.context.scene
	m=s.cam_machine
	if o.max.x-o.min.x>m.working_area.x or o.max.y-o.min.y>m.working_area.y or o.max.z-o.min.z>m.working_area.z:
		#o.max.x=min(o.min.x+m.working_area.x,o.max.x)
		#o.max.y=min(o.min.y+m.working_area.y,o.max.y)
		#o.max.z=min(o.min.z+m.working_area.z,o.max.z)
		o.warnings+='Operation exceeds your machine limits'
		
	#progress (o.min.x,o.min.y,o.min.z,o.max.x,o.max.y,o.max.z)
	
	

def samplePathLow(o,ch1,ch2,dosample):
	minx,miny,minz,maxx,maxy,maxz=o.min.x,o.min.y,o.min.z,o.max.x,o.max.y,o.max.z
	v1=Vector(ch1.points[-1])
	v2=Vector(ch2.points[0])
	
	v=v2-v1
	d=v.length
	v.normalize()
	
	vref=Vector((0,0,0))
	bpath=camPathChunk([])
	i=0
	while vref.length<d:
		i+=1
		vref=v*o.dist_along_paths*i
		if vref.length<d:
			p=v1+vref
			bpath.points.append([p.x,p.y,p.z])
	#print('between path')
	#print(len(bpath))
	pixsize=o.pixsize
	if dosample:
		if o.use_exact:
			cutterdepth=o.cutter_shape.dimensions.z/2
			for p in bpath.points:
				z=getSampleBullet(o.cutter_shape, p[0],p[1], cutterdepth, 1, o.minz)
				if z>p[2]:
					p[2]=z
		else:
			for p in bpath.points:
				xs=(p[0]-minx)/pixsize+o.borderwidth+pixsize/2#-m
				ys=(p[1]-miny)/pixsize+o.borderwidth+pixsize/2#-m
				z=getSampleImage((xs,ys),o.offset_image,o.minz)+o.skin
				if z>p[2]:
					p[2]=z
	return bpath


#def threadedSampling():#not really possible at all without running more blenders for same operation :( python!
#samples in both modes now - image and bullet collision too.
def sampleChunks(o,pathSamples,layers):
	#
	minx,miny,minz,maxx,maxy,maxz=o.min.x,o.min.y,o.min.z,o.max.x,o.max.y,o.max.z
	getAmbient(o)  

	if o.use_exact:#prepare collision world
		if o.update_bullet_collision_tag:
			prepareBulletCollision(o)
			
			o.update_bullet_collision_tag=False
		#print (o.ambient)
		cutter=o.cutter_shape
		cutterdepth=cutter.dimensions.z/2
	else:
		if o.strategy!='WATERLINE': # or prepare offset image, but not in some strategies.
			prepareArea(o)
		
		pixsize=o.pixsize
		
		coordoffset=o.borderwidth+pixsize/2#-m
		
		res=ceil(o.cutter_diameter/o.pixsize)
		m=res/2
		
	t=time.time()
	#print('sampling paths')
	
	totlen=0;#total length of all chunks, to estimate sampling time.
	for ch in pathSamples:
		totlen+=len(ch.points)
	layerchunks=[]
	minz=o.minz-0.000001#correction for image method problems
	layeractivechunks=[]
	lastrunchunks=[]
	
	for l in layers:
		layerchunks.append([])
		layeractivechunks.append(camPathChunk([]))
		lastrunchunks.append([])
			
	zinvert=0
	if o.inverse:
		ob=bpy.data.objects[o.object_name]
		zinvert=ob.location.z+maxz#ob.bound_box[6][2]
	
	n=0
	last_percent=-1
	#timing for optimisation
	samplingtime=timinginit()
	sortingtime=timinginit()
	totaltime=timinginit()
	timingstart(totaltime)
	lastz=minz
	
	for patternchunk in pathSamples:
		thisrunchunks=[]
		for l in layers:
			thisrunchunks.append([])
		lastlayer=None
		currentlayer=None
		lastsample=None
		#threads_count=4
		
		#for t in range(0,threads):
			
		for s in patternchunk.points:
			if o.strategy!='WATERLINE' and int(100*n/totlen)!=last_percent:
				last_percent=int(100*n/totlen)
				progress('sampling paths ',last_percent)
			n+=1
			x=s[0]
			y=s[1]
			if not o.ambient.isInside(x,y):
				newsample=(x,y,1)
			else:
				####sampling
				if o.use_exact:
					
					if lastsample!=None:#this is an optimalization, search only for near depths to the last sample. Saves about 30% of sampling time.
						z=getSampleBullet(cutter, x,y, cutterdepth, 1, lastsample[2]-o.dist_along_paths)#first try to the last sample
						if z<minz-1:
							z=getSampleBullet(cutter, x,y, cutterdepth, lastsample[2]-o.dist_along_paths, minz)
					else:
						z=getSampleBullet(cutter, x,y, cutterdepth, 1, minz)
					
					#print(z)
					#here we have 
				else:
					timingstart(samplingtime)
					xs=(x-minx)/pixsize+coordoffset
					ys=(y-miny)/pixsize+coordoffset
					timingadd(samplingtime)
					#if o.inverse:
					#  z=layerstart
					z=getSampleImage((xs,ys),o.offset_image,minz)+o.skin
				#if minz>z and o.ambient.isInside(x,y):
				#	z=minz;
				################################
				#handling samples
				############################################
				
				if minz>z:
					z=minz
				newsample=(x,y,z)
				#z=max(minz,z)
					
				#if sampled:# and (not o.inverse or (o.inverse)):uh what was this? disabled
				#	newsample=(x,y,z)
						
				#elif o.ambient_behaviour=='ALL' and not o.inverse:#handle ambient here, this should be obsolete,
				#	newsample=(x,y,minz)
			for i,l in enumerate(layers):
				terminatechunk=False
				
				ch=layeractivechunks[i]
				#print(i,l)
				#print(l[1],l[0])
				
				if l[1]<=newsample[2]<=l[0]:
					lastlayer=None #rather the last sample here ? has to be set to None, since sometimes lastsample vs lastlayer didn't fit and did ugly ugly stuff....
					if lastsample!=None:
						for i2,l2 in enumerate(layers):
							if l2[1]<=lastsample[2]<=l2[0]:
								lastlayer=i2
					
					currentlayer=i
					if lastlayer!=None and lastlayer!=currentlayer:# and lastsample[2]!=newsample[2]:#sampling for sorted paths in layers- to go to the border of the sampled layer at least...there was a bug here, but should be fixed.
						if currentlayer<lastlayer:
							growing=True
							r=range(currentlayer,lastlayer)
							spliti=1
						else:
							r=range(lastlayer,currentlayer)
							growing=False
							spliti=0
						#print(r)
						li=0
						for ls in r:
							splitz=layers[ls][1]
							#print(ls)
						
							v1=lastsample
							v2=newsample
							if o.protect_vertical:
								v1,v2=isVerticalLimit(v1,v2,o.protect_vertical_limit)
							v1=Vector(v1)
							v2=Vector(v2)
							#print(v1,v2)
							ratio=(splitz-v1.z)/(v2.z-v1.z)
							#print(ratio)
							betweensample=v1+(v2-v1)*ratio
							
							#ch.points.append(betweensample.to_tuple())
							
							if growing:
								if li>0:
									layeractivechunks[ls].points.insert(-1,betweensample.to_tuple())
								else:
									layeractivechunks[ls].points.append(betweensample.to_tuple())
								layeractivechunks[ls+1].points.append(betweensample.to_tuple())
							else:
								#print(v1,v2,betweensample,lastlayer,currentlayer)
								layeractivechunks[ls].points.insert(-1,betweensample.to_tuple())
								layeractivechunks[ls+1].points.insert(0,betweensample.to_tuple())
							
							li+=1
							#this chunk is terminated, and allready in layerchunks /
								
						#ch.points.append(betweensample.to_tuple())#
					ch.points.append(newsample)
				elif l[1]>newsample[2]:
					ch.points.append((newsample[0],newsample[1],l[1]))
				elif l[0]<newsample[2]:	 #terminate chunk
					terminatechunk=True

				if terminatechunk:
					if len(ch.points)>0:
						layerchunks[i].append(ch)
						thisrunchunks[i].append(ch)
						layeractivechunks[i]=camPathChunk([])
			lastsample=newsample
			
		for i,l in enumerate(layers):
			ch=layeractivechunks[i]
			if len(ch.points)>0:  
				
				#if o.stay_low and len(layerchunks[i])>0:
				#	between=samplePathLow(o,layerchunks[i][-1],ch)#this should be moved after sort
				#	layerchunks[i][-1].points.extend(between)
				#	layerchunks[i][-1].points.extend(ch.points) 
				#else:	
					
				layerchunks[i].append(ch)
				thisrunchunks[i].append(ch)
				layeractivechunks[i]=camPathChunk([])
				#parenting: not for outlinefilll!!! also higly unoptimized
			if (o.strategy=='PARALLEL' or o.strategy=='CROSS'):
				timingstart(sortingtime)
				parentChildDist(thisrunchunks[i], lastrunchunks[i],o)
				timingadd(sortingtime)

		lastrunchunks=thisrunchunks
				
			#print(len(layerchunks[i]))
	progress('checking relations between paths')
	timingstart(sortingtime)

	if (o.strategy=='PARALLEL' or o.strategy=='CROSS'):
		if len(layers)>1:# sorting help so that upper layers go first always
			for i in range(0,len(layers)-1):
				#print('layerstuff parenting')
				parentChild(layerchunks[i+1],layerchunks[i],o)
	timingadd(sortingtime)
	chunks=[]
	
	for i,l in enumerate(layers):
		if o.ramp:
			for ch in layerchunks[i]:
				ch.zstart=layers[i][0]
				ch.zend=layers[i][1]
		chunks.extend(layerchunks[i])
	timingadd(totaltime)
	timingprint(samplingtime)
	timingprint(sortingtime)
	timingprint(totaltime)
	return chunks  
	
def sampleChunksNAxis(o,pathSamples,layers):
	#
	minx,miny,minz,maxx,maxy,maxz=o.min.x,o.min.y,o.min.z,o.max.x,o.max.y,o.max.z
	
	#prepare collision world
	if o.update_bullet_collision_tag:
		prepareBulletCollision(o)
		#print('getting ambient')
		getAmbient(o)  
		o.update_bullet_collision_tag=False
	#print (o.ambient)
	cutter=o.cutter_shape
	cutterdepth=cutter.dimensions.z/2
		
	t=time.time()
	print('sampling paths')
	
	totlen=0;#total length of all chunks, to estimate sampling time.
	for ch in pathSamples:
		totlen+=len(ch.startpoints)
	layerchunks=[]
	minz=o.minz
	layeractivechunks=[]
	lastrunchunks=[]
	
	for l in layers:
		layerchunks.append([])
		layeractivechunks.append(camPathChunk([]))
		lastrunchunks.append([])
			
	n=0
	
	lastz=minz
	for patternchunk in pathSamples:
		#print (patternchunk.endpoints)
		thisrunchunks=[]
		for l in layers:
			thisrunchunks.append([])
		lastlayer=None
		currentlayer=None
		lastsample=None
		#threads_count=4
		lastrotation=(0,0,0)
		#for t in range(0,threads):
			
		for si,startp in enumerate(patternchunk.startpoints):
			if n/200.0==int(n/200.0):
				progress('sampling paths ',int(100*n/totlen))
			n+=1
			sampled=False
			#print(si)
			#print(patternchunk.points[si],patternchunk.endpoints[si])
			startp=Vector(patternchunk.startpoints[si])
			endp=Vector(patternchunk.endpoints[si])
			rotation=patternchunk.rotations[si]
			sweepvect=endp-startp
			sweepvect.normalize()
			####sampling
			if rotation!=lastrotation:
			
				cutter.rotation_euler=rotation
				if o.cutter_type=='VCARVE':
					cutter.rotation_euler.x+=pi
				bpy.context.scene.frame_set(0)
				#update scene here?
				
			#print(startp,endp)
			#samplestartp=startp+sweepvect*0.3#this is correction for the sweep algorithm to work better.
			newsample=getSampleBulletNAxis(cutter, startp, endp ,rotation, cutterdepth)

			
			################################
			#handling samples
			############################################
			if newsample!=None:#this is weird, but will leave it this way now.. just prototyping here.
				sampled=True
			else:
				newsample=endp
				sampled=True
				#print(newsample)
				
			#elif o.ambient_behaviour=='ALL' and not o.inverse:#handle ambient here
				#newsample=(x,y,minz)
			if sampled:
				for i,l in enumerate(layers):
					terminatechunk=False
					ch=layeractivechunks[i]
					#print(i,l)
					#print(l[1],l[0])
					v=startp-newsample
					distance=-v.length
					
					if l[1]<=distance<=l[0]:
						lastlayer=currentlayer
						currentlayer=i
						
						if lastsample!=None and lastlayer!=None and currentlayer!=None and lastlayer!=currentlayer:#sampling for sorted paths in layers- to go to the border of the sampled layer at least...there was a bug here, but should be fixed.
							if currentlayer<lastlayer:
								growing=True
								r=range(currentlayer,lastlayer)
								spliti=1
							else:
								r=range(lastlayer,currentlayer)
								growing=False
								spliti=0
							#print(r)
							li=0
							for ls in r:
								splitdistance=layers[ls][1]
							
								#v1=lastsample
								#v2=newsample
								#if o.protect_vertical:#different algo for N-Axis! need sto be perpendicular to or whatever.
								#	v1,v2=isVerticalLimit(v1,v2,o.protect_vertical_limit)
								#v1=Vector(v1)
								#v2=Vector(v2)
								#print(v1,v2)
								ratio=(splitdistance-lastdistance)/(distance-lastdistance)
								#print(ratio)
								betweensample=lastsample+(newsample-lastsample)*ratio
								#this probably doesn't work at all!!!! check this algoritm>
								betweenrotation=tuple_add(lastrotation,tuple_mul(tuple_sub(rotation,lastrotation),ratio))
								#startpoint = retract point, it has to be always available...
								betweenstartpoint=laststartpoint+(startp-laststartpoint)*ratio
								
								if growing:
									if li>0:
										layeractivechunks[ls].points.insert(-1,betweensample)
										layeractivechunks[ls].rotations.insert(-1,betweenrotation)
										layeractivechunks[ls].startpoints.insert(-1,betweenstartpoint)
									else:
										layeractivechunks[ls].points.append(betweensample)
										layeractivechunks[ls].rotations.append(betweenrotation)
										layeractivechunks[ls].startpoints.append(betweenstartpoint)
									layeractivechunks[ls+1].points.append(betweensample)
									layeractivechunks[ls+1].rotations.append(betweenrotation)
									layeractivechunks[ls+1].startpoints.append(betweenstartpoint)
								else:
									
									layeractivechunks[ls].points.insert(-1,betweensample)
									layeractivechunks[ls].rotations.insert(-1,betweenrotation)
									layeractivechunks[ls].startpoints.insert(-1,betweenstartpoint)
									layeractivechunks[ls+1].points.append(betweensample)
									layeractivechunks[ls+1].rotations.append(betweenrotation)
									layeractivechunks[ls+1].startpoints.append(betweenstartpoint)
									#layeractivechunks[ls+1].points.insert(0,betweensample)
								li+=1
								#this chunk is terminated, and allready in layerchunks /
									
							#ch.points.append(betweensample)#
						ch.points.append(newsample)
						ch.rotations.append(rotation)
						ch.startpoints.append(startp)
						lastdistance=distance
						
					
					elif l[1]>distance:
						v=sweepvect*l[1]
						p=startp-v
						ch.points.append(p)
						ch.rotations.append(rotation)
						ch.startpoints.append(startp)
					elif l[0]<distance:	 #retract to original track
						ch.points.append(startp)
						ch.rotations.append(rotation)
						ch.startpoints.append(startp)
						#terminatechunk=True
					'''
					if terminatechunk:
						#print(ch.points)
						if len(ch.points)>0:
							if len(ch.points)>0: 
								layerchunks[i].append(ch)
								thisrunchunks[i].append(ch)
								layeractivechunks[i]=camPathChunk([])
					'''
			#else:
			#	terminatechunk=True
			lastsample=newsample
			lastrotation=rotation
			laststartpoint=startp
		for i,l in enumerate(layers):
			ch=layeractivechunks[i]
			if len(ch.points)>0:  
				layerchunks[i].append(ch)
				thisrunchunks[i].append(ch)
				layeractivechunks[i]=camPathChunk([])
				#parenting: not for outlinefilll!!! also higly unoptimized
			if (o.strategy=='PARALLEL' or o.strategy=='CROSS'):
				parentChildDist(thisrunchunks[i], lastrunchunks[i],o)

		lastrunchunks=thisrunchunks
				
			#print(len(layerchunks[i]))
	
	progress('checking relations between paths')
	'''#this algorithm should also work for n-axis, but now is "sleeping"
	if (o.strategy=='PARALLEL' or o.strategy=='CROSS'):
		if len(layers)>1:# sorting help so that upper layers go first always
			for i in range(0,len(layers)-1):
				#print('layerstuff parenting')
				parentChild(layerchunks[i+1],layerchunks[i],o)
	'''
	chunks=[]
	for i,l in enumerate(layers):
		chunks.extend(layerchunks[i])
	
	'''
	
	'''
	return chunks  
	
def doSimulation(name,operations):
	'''perform simulation of operations. only for 3 axis'''
	o=operations[0]#initialization now happens from first operation, also for chains.
	getOperationSources(o)
	getBounds(o)#this is here because some background computed operations still didn't have bounds data
	sx=o.max.x-o.min.x
	sy=o.max.y-o.min.y

	resx=ceil(sx/o.simulation_detail)+2*o.borderwidth
	resy=ceil(sy/o.simulation_detail)+2*o.borderwidth

	si=numpy.array((0.1),dtype=float)
	si.resize(resx,resy)
	si.fill(0)
	
	for o in operations:
		verts=bpy.data.objects[o.path_object_name].data.vertices
		
		cutterArray=getCutterArray(o,o.simulation_detail)
		#cb=cutterArray<-1
		#cutterArray[cb]=1
		cutterArray=-cutterArray
		m=int(cutterArray.shape[0]/2)
		size=cutterArray.shape[0]
		print(si.shape)
		#for ch in chunks:
		lasts=verts[1].co
		l=len(verts)
		perc=-1
		vtotal=len(verts)
		for i,vert in enumerate(verts):
			if perc!=int(100*i/vtotal):
				perc=int(100*i/vtotal)
				progress('simulation',perc)
			#progress('simulation ',int(100*i/l))
			if i>0:
				s=vert.co
				v=s-lasts
				
				if v.length>o.simulation_detail:
					l=v.length
					
					v.length=o.simulation_detail
					while v.length<l:
						
						xs=(lasts.x+v.x-o.min.x)/o.simulation_detail+o.borderwidth+o.simulation_detail/2#-m
						ys=(lasts.y+v.y-o.min.y)/o.simulation_detail+o.borderwidth+o.simulation_detail/2#-m
						z=lasts.z+v.z
						if xs>m+1 and xs<si.shape[0]-m-1 and ys>m+1 and ys<si.shape[1]-m-1 :
							si[xs-m:xs-m+size,ys-m:ys-m+size]=numpy.minimum(si[xs-m:xs-m+size,ys-m:ys-m+size],cutterArray+z)
						v.length+=o.simulation_detail
			
				xs=(s.x-o.min.x)/o.simulation_detail+o.borderwidth+o.simulation_detail/2#-m
				ys=(s.y-o.min.y)/o.simulation_detail+o.borderwidth+o.simulation_detail/2#-m
				if xs>m+1 and xs<si.shape[0]-m-1 and ys>m+1 and ys<si.shape[1]-m-1 :
					si[xs-m:xs-m+size,ys-m:ys-m+size]=numpy.minimum(si[xs-m:xs-m+size,ys-m:ys-m+size],cutterArray+s.z)
					
				lasts=s
				
	o=operations[0]
	si=si[o.borderwidth:-o.borderwidth,o.borderwidth:-o.borderwidth]
	si+=-o.min.z
	oname='csim_'+name
	
	cp=getCachePath(o)[:-len(o.name)]+name
	iname=cp+'_sim.exr'
	inamebase=bpy.path.basename(iname)
	print(si.shape[0],si.shape[1])
	i=numpysave(si,iname)
		
	
	
	#if inamebase in bpy.data.images:
	#	i=bpy.data.images[inamebase]
	#	i.reload()
	#else:
	i=bpy.data.images.load(iname)

	if oname in bpy.data.objects:
		ob=bpy.data.objects[oname]
	else:
		bpy.ops.mesh.primitive_plane_add(view_align=False, enter_editmode=False, location=(0,0,0), rotation=(0, 0, 0))
		ob=bpy.context.active_object
		ob.name=oname
		
		bpy.ops.object.modifier_add(type='SUBSURF')
		ss=ob.modifiers[-1]
		ss.subdivision_type='SIMPLE'
		ss.levels=5
		ss.render_levels=6
		bpy.ops.object.modifier_add(type='SUBSURF')
		ss=ob.modifiers[-1]
		ss.subdivision_type='SIMPLE'
		ss.levels=3
		ss.render_levels=3
		bpy.ops.object.modifier_add(type='DISPLACE')
	
	ob.location=((o.max.x+o.min.x)/2,(o.max.y+o.min.y)/2,o.min.z)
	ob.scale.x=(o.max.x-o.min.x)/2
	ob.scale.y=(o.max.y-o.min.y)/2	
	print(o.max.x, o.min.x)
	print(o.max.y, o.min.y)
	print('bounds')
	disp=ob.modifiers[-1]
	disp.direction='Z'
	disp.texture_coords='LOCAL'
	disp.mid_level=0
	
	if oname in bpy.data.textures:
		t=bpy.data.textures[oname]
		
		t.type='IMAGE'
		disp.texture=t
		
		
		t.image=i
	else:
		bpy.ops.texture.new()
		for t in bpy.data.textures:
			if t.name=='Texture':
				t.type='IMAGE'
				t.name=oname
				t=t.type_recast()
				t.type='IMAGE'
				t.image=i
				disp.texture=t
	ob.hide_render=True
	
def chunksToMesh(chunks,o):
	##########convert sampled chunks to path, optimization of paths
	t=time.time()
	s=bpy.context.scene
	origin=(0,0,o.free_movement_height)	 
	verts = [origin]
	if o.axes!='3':
		verts_rotations=[(0,0,0)]
	progress('building paths from chunks')
	e=0.0001
	lifted=True
	test=bpy.app.debug_value
	edges=[]	
	
	for chi in range(0,len(chunks)):
		#print(chi)
		ch=chunks[chi]
		nverts=[]
		if o.optimize:
			ch=optimizeChunk(ch,o)
		
		#lift and drop
		
		if lifted:
			if o.axes=='3' or o.axes=='5':
				v=(ch.points[0][0],ch.points[0][1],o.free_movement_height)
			else:
				v=ch.startpoints[0]#startpoints=retract points
				verts_rotations.append(ch.rotations[0])
			verts.append(v)
		#scount=len(verts)
		verts.extend(ch.points)
		#ecount=len(verts)
		#for a in range(scount,ecount-1):
		#	edges.append((a,a+1))
		if o.axes!='3' and o.axes!='5':
			verts_rotations.extend(ch.rotations)
			
		lift = True
		if chi<len(chunks)-1:#TODO: remake this for n axis
			#nextch=
			last=Vector(ch.points[-1])
			first=Vector(chunks[chi+1].points[0])
			vect=first-last
			if (o.strategy=='PARALLEL' or o.strategy=='CROSS') and vect.z==0 and vect.length<o.dist_between_paths*2.5:#case of neighbouring paths
				lift=False
			if abs(vect.x)<e and abs(vect.y)<e:#case of stepdown by cutting.
				lift=False
			
		if lift:
			if o.axes== '3' or o.axes=='5':
				v=(ch.points[-1][0],ch.points[-1][1],o.free_movement_height)
			else:
				v=ch.startpoints[-1]
				verts_rotations.append(ch.rotations[-1])
			verts.append(v)
		lifted=lift
		#print(verts_rotations)
	if o.use_exact:
		cleanupBulletCollision(o)
	print(time.time()-t)
	t=time.time()
	
	#actual blender object generation starts here:
	edges=[]	
	for a in range(0,len(verts)-1):
		edges.append((a,a+1))
	
	oname="cam_path_"+o.name
		
	mesh = bpy.data.meshes.new(oname)
	mesh.name=oname
	mesh.from_pydata(verts, edges, [])
	if o.axes!='3':
		x=[]
		y=[]
		z=[]
		for a,b,c in verts_rotations:#TODO: optimize this. this is just rewritten too many times...
			#print(r)
			x.append(a)
			y.append(b)
			z.append(c)
			
		mesh['rot_x']=x
		mesh['rot_y']=y
		mesh['rot_z']=z
		

	if oname in s.objects:
		s.objects[oname].data=mesh
		ob=s.objects[oname]
	else: 
		ob=object_utils.object_data_add(bpy.context, mesh, operator=None)
		ob=ob.object
		
	print(time.time()-t)
	
	ob.location=(0,0,0)
	o.path_object_name=oname
	if o.auto_export:
		exportGcodePath(o.filename,[ob.data],[o])

	
def exportGcodePath(filename,vertslist,operations):
	'''exports gcode with the heeks cnc adopted library.'''
	#verts=[verts]
	#operations=[o]#this is preparation for actual chain exporting
	progress('exporting gcode file')
	t=time.time()
	s=bpy.context.scene
	m=s.cam_machine
	
	#find out how many files will be done:
	
	split=False
	
	totops=0
	findex=0
	if m.eval_splitting:#detect whether splitting will happen
		for mesh in vertslist:
			totops+=len(mesh.vertices)
		print(totops)
		if totops>m.split_limit:
			split=True
			filesnum=ceil(totops/m.split_limit)
			print('file will be separated into %i files' % filesnum)
	print('1')	
	
	basefilename=bpy.data.filepath[:-len(bpy.path.basename(bpy.data.filepath))]+safeFileName(filename)
	
	from . import nc
	extension='.tap'
	if m.post_processor=='ISO':
		from .nc import iso as postprocessor
	if m.post_processor=='MACH3':
		from .nc import mach3 as postprocessor
	elif m.post_processor=='EMC':
		extension = '.ngc'
		from .nc import emc2b as postprocessor
	elif m.post_processor=='HM50':
		from .nc import hm50 as postprocessor
	elif m.post_processor=='HEIDENHAIN':
		extension='.H'
		from .nc import heiden as postprocessor
	elif m.post_processor=='TNC151':
		from .nc import tnc151 as postprocessor
	elif m.post_processor=='SIEGKX1':
		from .nc import siegkx1 as postprocessor
	elif m.post_processor=='CENTROID':
		from .nc import centroid1 as postprocessor
	elif m.post_processor=='ANILAM':
		from .nc import anilam_crusader_m as postprocessor
	
	
	
	if s.unit_settings.system=='METRIC':
		unitcorr=1000.0
	else:
		unitcorr=1/0.0254;
	rotcorr=180.0/pi
	
	def startNewFile():
		fileindex=''
		if split:
			fileindex='_'+str(findex)
		filename=basefilename+fileindex+extension
		c=postprocessor.Creator()
		c.file_open(filename)
	
		#unit system correction
		###############
		if s.unit_settings.system=='METRIC':
			c.metric()
		else:
			c.imperial()
		#start program
		c.program_begin(0,filename)
		c.comment('G-code generated with BlenderCAM and NC library')
		#absolute coordinates
		c.absolute()
		#work-plane, by now always xy, 
		c.set_plane(0)
		c.flush_nc()
		return c
		
	c=startNewFile()
	
	processedops=0
	for i,o in enumerate(operations):
		mesh=vertslist[i]
		verts=mesh.vertices[:]
		if o.axes!='3':
			rx=mesh['rot_x']
			ry=mesh['rot_y']
			rz=mesh['rot_z']
			
		#spindle rpm and direction
		###############
		if o.spindle_rotation_direction=='CW':
			spdir_clockwise=True
		else:
			spdir_clockwise=False

		#write tool, not working yet probably 
		c.comment('Tool change')
		c.tool_change(o.cutter_id)
		c.spindle(o.spindle_rpm,spdir_clockwise)
		c.feedrate(unitcorr*o.feedrate)
		c.flush_nc()
		
		
		#commands=[]
		m=bpy.context.scene.cam_machine
		
		millfeedrate=min(o.feedrate,m.feedrate_max)
		millfeedrate=unitcorr*max(millfeedrate,m.feedrate_min)
		plungefeedrate= millfeedrate*o.plunge_feedrate/100
		freefeedrate=m.feedrate_max*unitcorr
		
		last=Vector((0.0,0.0,o.free_movement_height))#nonsense values so first step of the operation gets written for sure
		lastrot=Euler((0,0,0))
		duration=0.0
		f=millfeedrate
		downvector= Vector((0,0,-1))
		plungelimit=(pi/2-o.plunge_angle)
		print('2')
		for vi,vert in enumerate(verts):
			v=vert.co
			if o.axes!='3':
				v=v.copy()#we rotate it so we need to copy the vector
				r=Euler((rx[vi],ry[vi],rz[vi]))
				#conversion to N-axis coordinates
				# this seems to work correctly
				rcompensate=r.copy()
				rcompensate.x=-r.x
				rcompensate.y=-r.y
				rcompensate.z=-r.z
				v.rotate(rcompensate)
				
				if r.x==lastrot.x: ra=None;
				else:	ra=r.x*rotcorr
				if r.y==lastrot.y: rb=None;
				else:	rb=r.y*rotcorr

			if vi>0 and v.x==last.x: vx=None; 
			else:	vx=v.x*unitcorr
			if vi>0 and v.y==last.y: vy=None; 
			else:	vy=v.y*unitcorr
			if vi>0 and v.z==last.z: vz=None; 
			else:	vz=v.z*unitcorr
			
			#v=(v.x*unitcorr,v.y*unitcorr,v.z*unitcorr)
			vect=v-last
			l=vect.length
			if vi>0	 and l>0 and downvector.angle(vect)<plungelimit:
				#print('plunge')
				#print(vect)
				if f!=plungefeedrate:
					f=plungefeedrate
					c.feedrate(plungefeedrate)
					
				if o.axes=='3':
					c.feed( x=vx, y=vy, z=vz )
				else:
					#print(ra,rb)
					c.feed( x=vx, y=vy, z=vz ,a = ra, b = rb)
					
			elif v.z>=o.free_movement_height or vi==0:#v.z==last.z==o.free_movement_height or vi==0
			
				if f!=freefeedrate:
					f=freefeedrate
					c.feedrate(freefeedrate)
					
				if o.axes=='3':
					c.rapid( x = vx , y = vy , z = vz )
				else:
					c.rapid(x=vx, y=vy, z = vz, a = ra, b = rb)
				#gcommand='{RAPID}'
				
			else:
			
				if f!=millfeedrate:
					f=millfeedrate
					c.feedrate(millfeedrate)
					
				if o.axes=='3':
					c.feed(x=vx,y=vy,z=vz)
				else:
					c.feed( x=vx, y=vy, z=vz ,a = ra, b = rb)

			
			duration+=vect.length/f
			#print(duration)
			last=v
			if o.axes!='3':
				lastrot=r
				
			processedops+=1
			if split and processedops>m.split_limit:
				c.rapid(x=last.x*unitcorr,y=last.y*unitcorr,z=o.free_movement_height*unitcorr)
				#@v=(ch.points[-1][0],ch.points[-1][1],o.free_movement_height)
				findex+=1
				c.file_close()
				c=startNewFile()
				c.spindle(o.spindle_rpm,spdir_clockwise)
				c.feedrate(unitcorr*o.feedrate)
				c.flush_nc()
				c.rapid(x=last.x*unitcorr,y=last.y*unitcorr,z=o.free_movement_height*unitcorr)
				c.rapid(x=last.x*unitcorr,y=last.y*unitcorr,z=last.z*unitcorr)
				processedops=0
			
	o.duration=duration*unitcorr
	#print('duration')
	#print(o.duration)
	
	
	c.program_end()
	c.file_close()
	print(time.time()-t)

def orderPoly(polys):	#sor poly, do holes e.t.c.
	p=Polygon.Polygon()
	levels=[[],[],[],[],[],[],[],[],[],[],[],[],[],[],[],[],[],[],[],[],[],[],[],[],[],[],[],[],[],[]] 
	for ppart in polys:
		hits=0
		for ptest in polys:
			
			if ppart!=ptest:
				#print (ppart[0][0])
				if ptest.isInside(ppart[0][0][0],ppart[0][0][1]):
					hits+=1
		#hole=0
		#if hits % 2 ==1:
		 # hole=1
		if ppart.nPoints(0)>0:
			ppart.simplify()
			levels[hits].append(ppart)
	li=0
	for l in levels:	
		
		if li%2==1:
			for part in l:
				p=p-part
			#hole=1
		else:
			for part in l:
				p=p+part
			
		if li==1:#last chance to simplify stuff... :)
			p.simplify()
		li+=1
	  
	return p

def curveToPolys(cob):
	chunks=curveToChunks(cob)
	polys=chunksToPolys(chunks)
	return polys

def silhoueteOffset(context,offset):
	bpy.context.scene.cursor_location=(0,0,0)
	ob=bpy.context.active_object
	if ob.type=='CURVE':
		plist=curveToPolys(ob)
	else:
		plist=getObjectSilhouete('OBJECTS',[ob])
	p=Polygon.Polygon()
	for p1 in plist:
		p+=p1
	p=outlinePoly(p,abs(offset),64,True,abs(offset)*0.002,offset>0)
	#print(p[0])
	#p.shift(ob.location.x,ob.location.y)
	polyToMesh('offset curve',p,ob.location.z)
	
	
	return {'FINISHED'}
	
def polygonBoolean(context,boolean_type):
	bpy.context.scene.cursor_location=(0,0,0)
	ob=bpy.context.active_object
	obs=[]
	for ob1 in bpy.context.selected_objects:
		if ob1!=ob:
			obs.append(ob1)
	plist=curveToPolys(ob)
	p1=Polygon.Polygon()
	for pt in plist:
		p1+=pt
	polys=[]
	for o in obs:
		plist=curveToPolys(o)
		p2=Polygon.Polygon()
		for p in plist:
			p2+=p
		polys.append(p2)
	#print(polys)
	if boolean_type=='UNION':
		for p2 in polys:
			p1=p1+p2
	elif boolean_type=='DIFFERENCE':
		for p2 in polys:
			p1=p1-p2
	elif boolean_type=='INTERSECT':
		for p2 in polys:
			p1=p1 & p2
		
	polyToMesh('boolean',p1,ob.location.z)
	#bpy.ops.object.convert(target='CURVE')
	#bpy.context.scene.cursor_location=ob.location
	#bpy.ops.object.origin_set(type='ORIGIN_CURSOR')

	return {'FINISHED'}
		
'''
def chunksToPoly(chunks):
	
	verts=[]
	pverts=[]
	p=Polygon.Polygon()
	#contourscount=0
	polys=[]
	
	for ch in chunks:
		pchunk=[]
		for v in ch:
			pchunk.append((v[0],v[1]))
		
		if len(pchunk)>1:
			polys.append(Polygon.Polygon(pchunk)) 
	levels=[[],[],[],[],[],[],[],[],[],[],[],[],[],[],[],[],[],[],[],[],[]] 
	for ppart in polys:
		hits=0
		for ptest in polys:
			
			if ppart!=ptest:
				#print (ppart[0][0])
				if ptest.isInside(ppart[0][0][0],ppart[0][0][1]):
					hits+=1
		#hole=0
		#if hits % 2 ==1:
		 # hole=1
		if ppart.nPoints(0)>0:
			ppart.simplify()
			levels[hits].append(ppart)
	li=0
	for l in levels:	
		
		if li%2==1:
			for part in l:
				p=p-part
			#hole=1
		else:
			for part in l:
				p=p+part
			
		if li==1:#last chance to simplify stuff... :)
			p.simplify()
		li+=1
	  
	return p
'''



def Helix(r,np, zstart,pend,rev):
	c=[]
	pi=math.pi
	v=mathutils.Vector((r,0,zstart))
	e=mathutils.Euler((0,0,2.0*pi/np))
	zstep=(zstart-pend[2])/(np*rev)
	for a in range(0,int(np*rev)):
		c.append((v.x+pend[0],v.y+pend[1],zstart-(a*zstep)))
		v.rotate(e)
	c.append((v.x+pend[0],v.y+pend[1],pend[2]))
		
	return c
	

def comparezlevel(x):
	return x[5]

def overlaps(bb1,bb2):#true if bb1 is child of bb2
	ch1=bb1
	ch2=bb2
	if (ch2[1]>ch1[1]>ch1[0]>ch2[0] and ch2[3]>ch1[3]>ch1[2]>ch2[2]):
		return True

def sortChunks(chunks,o):
	if o.strategy!='WATERLINE':
		progress('sorting paths')
	sys.setrecursionlimit(100000)# the getNext() function of CamPathChunk was running out of recursion limits.
	sortedchunks=[]
	
	lastch=None
	i=len(chunks)
	pos=(0,0,0)
	#for ch in chunks:
	#	ch.getNext()#this stores the unsortedchildren properties
	#print('numofchunks')
	#print(len(chunks))
	while len(chunks)>0:
		ch=None
		if len(sortedchunks)==0 or len(lastch.parents)==0:#first chunk or when there are no parents -> parents come after children here...
			#ch=-1
			mind=10000
			d=100000000000
			
			for chtest in chunks:
				cango=True
				for child in chtest.children:# here was chtest.getNext==chtest, was doing recursion error and slowing down.
					if child.sorted==False:
						cango=False
						break;
				if cango:
					d=chtest.dist(pos,o)
					if d<mind:
						ch=chtest
						mind=d
		elif len(lastch.parents)>0:# looks in parents for next candidate, recursively
			for parent in lastch.parents:
				ch=parent.getNext()
				break
			
		if ch!=None:#found next chunk
			ch.sorted=True
			ch.adaptdist(pos,o)
			chunks.remove(ch)
			
			mergedist=3*o.dist_between_paths
			if o.strategy=='PENCIL':#this is bigger for pencil path since it goes on the surface to clean up the rests, and can go to close points on the surface without fear of going deep into material.
				mergedist=10*o.dist_between_paths
			if o.stay_low and lastch!=None and not(o.strategy=='CARVE' and o.carve_depth>0) and (ch.distStart(pos,o)<mergedist or (o.parallel_step_back and ch.distStart(pos,o)<2*mergedist)):
				#CARVE should lift allways, when it goes below surface...
				#print(mergedist,ch.dist(pos,o))
				if o.strategy=='PARALLEL' or o.strategy=='CROSS' or o.strategy=='PENCIL':# for these paths sorting happens after sampling, thats why they need resample the connection
					between=samplePathLow(o,lastch,ch,True)
				else:
					between=samplePathLow(o,lastch,ch,False)#other paths either dont use sampling or are sorted before it.
			
				sortedchunks[-1].points.extend(between.points)
				sortedchunks[-1].points.extend(ch.points)
			else:
				sortedchunks.append(ch)
			lastch=ch
			pos=lastch.points[-1]
		i-=1	
		'''
		if i<-200:
			for ch in chunks:
				print(ch.sorted)
				print(ch.getNext())
				print(len(ch.points))
		'''
	sys.setrecursionlimit(1000)

	return sortedchunks

def testbite(pos):
	xs=(pos.x-o.min.x)/o.simulation_detail+o.borderwidth+o.simulation_detail/2#-m
	ys=(pos.y-o.min.y)/o.simulation_detail+o.borderwidth+o.simulation_detail/2#-m
	z=pos.z
	m=int(o.cutterArray.shape[0]/2)

	if xs>m+1 and xs<o.millimage.shape[0]-m-1 and ys>m+1 and ys<o.millimage.shape[1]-m-1 :
		o.millimage[xs-m:xs-m+size,ys-m:ys-m+size]=numpy.minimum(o.millimage[xs-m:xs-m+size,ys-m:ys-m+size],cutterArray+z)
	v.length+=o.simulation_detail
	

	


def getVectorRight(lastv,verts):#most right vector from a set
	defa=100
	v1=Vector(lastv[0])
	v2=Vector(lastv[1])
	va=v2-v1
	for i,v in enumerate(verts):
		if v!=lastv[0]:
			vb=Vector(v)-v2
			a=va.angle_signed(Vector(vb))
			#if a<=0:
			#	a=2*pi+a
			
			if a<defa:
				defa=a
				returnvec=i
	return returnvec

def cleanUpDict(ndict):
	print('removing lonely points')#now it should delete all junk first, iterate over lonely verts.
	#found_solitaires=True
	#while found_solitaires:
	found_solitaires=False
	keys=[]
	keys.extend(ndict.keys())
	removed=0
	for k in keys:
		print(k)
		print(ndict[k])
		if len(ndict[k])<=1:
			newcheck=[k]
			while(len(newcheck)>0):
				v=newcheck.pop()
				if len(ndict[v])<=1:
					for v1 in ndict[v]:
						newcheck.append(v)
					dictRemove(ndict,v)
			removed+=1
			found_solitaires=True
	print(removed)
	
def dictRemove(dict,val):
	for v in dict[val]:
		dict[v].remove(val)
	dict.pop(val)

def getArea(poly):
	return poly.area()	

def addLoop(parentloop, start, end):
	added=False
	for l in parentloop[2]:
		if l[0]<start and l[1]>end:
			addLoop(l,start,end)
			return
	parentloop[2].append([start,end,[]])
	
def cutloops(csource,parentloop,loops):
	copy=csource[parentloop[0]:parentloop[1]]
	
	for li in range(len(parentloop[2])-1,-1,-1):
		l=parentloop[2][li]
		#print(l)
		copy=copy[:l[0]-parentloop[0]]+copy[l[1]-parentloop[0]:]
	loops.append(copy)
	for l in parentloop[2]:
		cutloops(csource,l,loops)

def getOperationSilhouete(operation):
	'''gets silhouete for the operation
		uses image thresholding for everything except curves.
	'''
	if operation.update_silhouete_tag:
		image=None
		objects=None
		if operation.geometry_source=='OBJECT' or operation.geometry_source=='GROUP':
			if operation.onlycurves==False:
				stype='OBJECTS'
			else:
				stype='CURVES'
		else:
			stype='IMAGE'
		if stype == 'OBJECTS' or stype=='IMAGE':
			print('image method')
			samples = renderSampleImage(operation)
			if stype=='OBJECTS':
				i = samples > operation.minz-0.0000001#numpy.min(operation.zbuffer_image)-0.0000001##the small number solves issue with totally flat meshes, which people tend to mill instead of proper pockets. then the minimum was also maximum, and it didn't detect contour.
			else:
				i = samples > numpy.min(operation.zbuffer_image)#this fixes another numeric imprecision.
				
			chunks=	imageToChunks(operation,i)
			operation.silhouete=chunksToPolys(chunks)
			#print(operation.silhouete)
			#this conversion happens because we need the silh to be oriented, for milling directions.
		else:
			print('object method')#this method is currently used only for curves. This is because exact silh for objects simply still doesn't work...
			operation.silhouete=getObjectSilhouete(stype, objects=operation.objects)
				
		operation.update_silhouete_tag=False
	return operation.silhouete
		
def getObjectSilhouete(stype, objects=None):
	#o=operation
	if stype=='CURVES':#curve conversion to polygon format
		allchunks=[]
		for ob in objects:
			chunks=curveToChunks(ob)
			allchunks.extend(chunks)
		silhouete=chunksToPolys(allchunks)
		
	elif stype=='OBJECTS':
		totfaces=0
		for ob in objects:
			totfaces+=len(ob.data.polygons)
			
		if totfaces<20000:#boolean polygons method
			t=time.time()
			print('shapely getting silhouette')
			polys=[]
			for ob in objects:
				
				m=ob.data
				mw =ob.matrix_world
				mwi = mw.inverted()
				r=ob.rotation_euler
				m.calc_tessface()
				id=0
				e=0.000001
				scaleup=100
				for f in m.tessfaces:
					n=f.normal.copy()
					n.rotate(r)
					#verts=[]
					#for i in f.vertices:
					#	verts.append(mw*m.vertices[i].co)
					#n=mathutils.geometry.normal(verts[0],verts[1],verts[2])
					if n.z>0.0 and f.area>0.0 :
						s=[]
						c=f.center.xy
						for i in f.vertices:
							v=mw* m.vertices[i].co
							x=v.x
							y=v.y
							x=x+(x-c.x)*e
							y=y+(y-c.y)*e
							s.append((x,y))
						if len(v)>2:
							p=spolygon.Polygon(s)
							#print(dir(p))
							polys.append(p)
						#if id==923:
						#	m.polygons[923].select
						id+=1	
			#print(polys)
			p=sops.unary_union(polys)
			print(time.time()-t)
			
			t=time.time()
			silhouete = [polygon_utils_cam.Shapely2Polygon(p)]
			'''
			e=0.00001#one hunderth of a millimeter, should be ok.
			origtol=Polygon.getTolerance()
			print(origtol)
			Polygon.setTolerance(e)	
			print('detecting silhouete - boolean based')
			ob=objects[0]
			m=ob.data
			polys=[]
			m.calc_tessface()
			for f in m.tessfaces:
				if f.normal.z>0 and f.area>0:
					s=[]
					for i in f.vertices:
						v=m.vertices[i].co
						s.append((v.x,v.y))
					if len(v)>2:
						p=Polygon.Polygon(s)
						#print(dir(p))
						polys.append(p)

			#print(polys)
			silh=Polygon.Polygon()
			for p in polys:
				silh+=p
				
			#clean 0 area parts of the silhouete
			
				
			nsilh=Polygon.Polygon()
			for i in range(0,len(silh)):
				if i not in remove:
					nsilh.addContour(silh[i],silh.isHole(i))
			silh=nsilh
			#silh.simplify()
			silh.shift(ob.location.x,ob.location.y)
			silhouete=[silh]
			Polygon.setTolerance(origtol)
			'''
	return silhouete
	
def getAmbient(o):
	if o.update_ambient_tag:
		if o.ambient_cutter_restrict:#cutter stays in ambient & limit curve
			m=o.cutter_diameter/2
		else: m=0

		if o.ambient_behaviour=='AROUND':
			r=o.ambient_radius - m
			o.ambient = getObjectOutline( r , o , True)# in this method we need ambient from silhouete
		else:
			o.ambient=Polygon.Polygon(((o.min.x + m ,o.min.y + m ) , (o.min.x + m ,o.max.y - m ),(o.max.x - m ,o.max.y - m ),(o.max.x - m , o.min.y + m )))
		
		if o.use_limit_curve:
			if o.limit_curve!='':
				limit_curve=bpy.data.objects[o.limit_curve]
				polys=curveToPolys(limit_curve)
				o.limit_poly=Polygon.Polygon()
				for p in polys:
					o.limit_poly+=p
				if o.ambient_cutter_restrict:
					o.limit_poly = outlinePoly(o.limit_poly,o.cutter_diameter/2,o.circle_detail,o.optimize,o.optimize_threshold,offset = False)
			o.ambient = o.ambient & o.limit_poly
	o.update_ambient_tag=False
	
def getObjectOutline(radius,o,Offset):
	
	polygons=getOperationSilhouete(o)
	outline=Polygon.Polygon()
	i=0
	#print('offseting polygons')
		
	outlines=[]
	for p in polygons:#sort by size before this???
		
		
		if radius>0:
			p=outlinePoly(p,radius,o.circle_detail,o.optimize,o.optimize_threshold,Offset)
					
		if o.dont_merge:
			for ci in range(0,len(p)):
				outline.addContour(p[ci],p.isHole(ci))
		else:
			#print(p)
			outline=outline+p
	return outline
	
def addOrientationObject(o):
	name = o.name+' orientation'
	s=bpy.context.scene
	if s.objects.find(name)==-1:
		bpy.ops.object.empty_add(type='SINGLE_ARROW', view_align=False, location=(0,0,0))

		ob=bpy.context.active_object
		ob.empty_draw_size=0.05
		ob.show_name=True
		ob.name=name

def removeOrientationObject(o):
	name=o.name+' orientation'
	if bpy.context.scene.objects.find(name)>-1:
		ob=bpy.context.scene.objects[name]
		delob(ob)

def addMachineAreaObject():
	
	s=bpy.context.scene
	ao=bpy.context.active_object
	if s.objects.get('CAM_machine')!=None:
	   o=s.objects['CAM_machine']
	else:
		bpy.ops.mesh.primitive_cube_add(view_align=False, enter_editmode=False, location=(1, 1, -1), rotation=(0, 0, 0))
		o=bpy.context.active_object
		o.name='CAM_machine'
		o.data.name='CAM_machine'
		bpy.ops.object.transform_apply(location=True, rotation=False, scale=False)
		o.draw_type = 'WIRE'
		bpy.ops.object.editmode_toggle()
		bpy.ops.mesh.delete(type='ONLY_FACE')
		bpy.ops.mesh.select_mode(use_extend=False, use_expand=False, type='EDGE', action='TOGGLE')
		bpy.ops.mesh.select_all(action='TOGGLE')
		bpy.ops.mesh.subdivide(number_cuts=32, smoothness=0, quadtri=False, quadcorner='STRAIGHT_CUT', fractal=0, fractal_along_normal=0, seed=0)
		bpy.ops.mesh.select_nth(nth=2, offset=0)
		bpy.ops.mesh.delete(type='EDGE')
		bpy.ops.object.editmode_toggle()
		o.hide_render = True
		o.hide_select = True
		o.select=False
	#bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)
	   
	o.dimensions=bpy.context.scene.cam_machine.working_area
	if ao!=None:
		activate(ao)
	else:
		bpy.context.scene.objects.active=None

def getBridges(p,o):
	# this function finds positions of the bridges, and returns these.
	pass;
def addBridges(ch,o,z):
	#this functions adds Bridges to the finished chunks.
	ch.getLength()
	n=int(ch.length/o.bridges_max_distance)
	bpc=o.bridges_per_curve
	if o.bridges_width*bpc>ch.length/2:
		bpc=math.floor(ch.length/(2*o.bridges_width))
	n = max(n,bpc)
	if n>0:
		dist=ch.length/n
		pos=[]
		for i in range(0,n):
			pos.append([i*dist+0.00001+dist/2.0,i*dist+0.00001+dist/2.0+o.bridges_width+o.cutter_diameter])
		dist=0
		bridgeheight=min(0,o.min.z+o.bridges_height)
		inbridge=False
		posi=0
		insertpoints=[]
		changepoints=[]
		vi=0
		while vi<len(ch.points):
			v1=ch.points[vi]
			v2=Vector(v1)#this is for case of last point and not closed chunk..
			if ch.closed and vi==len(ch.points)-1:
				v2=Vector(ch.points[0])
			elif vi+1<len(ch.points):
				v2=Vector(ch.points[vi+1])
			v1=Vector(v1)
			#if v1.z<bridgeheight or v2.z<bridgeheight:
			v=v2-v1
			dist+=v.length
			
			wasinbridge=inbridge
			if not inbridge and posi<len(pos) and pos[posi][0]<dist:#detect start of bridge
				
				ratio=(dist-pos[posi][0])/v.length
				point1=v2-v*ratio#TODO: optimize this : how? what was meant by the initial comment?
				point2=v2-v*ratio
				if bridgeheight>point1.z:
					point1.z=min(point1.z,bridgeheight)
					point2.z=max(point2.z,bridgeheight)
					#ch.points.insert(vi-1,point1)
					#ch.points.insert(vi,point2)
					insertpoints.append([vi+1,point1.to_tuple()])
					insertpoints.append([vi+1,point2.to_tuple()])
				inbridge=True
				
			if wasinbridge and inbridge:#still in bridge, raise the point up.#
				changepoints.append([vi,(v1.x,v1.y,max(v1.z,bridgeheight))])
				#ch.points[vi]=(v1.x,v1.y,max(v1.z,bridgeheight))
				
			if inbridge and pos[posi][1]<dist:#detect end of bridge
				ratio=(dist-pos[posi][1])/v.length
				point1=v2-v*ratio
				point2=v2-v*ratio
				if bridgeheight>point1.z:
					point1.z=max(point1.z,bridgeheight)
					point2.z=min(point2.z,bridgeheight)
					#ch.points.insert(vi,point1)
					#ch.points.insert(vi+1,point2)
					#vi+=2
					insertpoints.append([vi+1,point1.to_tuple()])
					insertpoints.append([vi+1,point2.to_tuple()])
				inbridge=False
				posi+=1 
				vi-=1
				dist-=v.length
			vi+=1
				
			
			
			
			if posi>=len(pos):
				#print('added bridges')
				break;
		for p in changepoints:
			ch.points[p[0]]=p[1]
		for pi in range(len(insertpoints)-1,-1,-1):
			ch.points.insert(insertpoints[pi][0],insertpoints[pi][1])
#this is the main function.

def getPath3axis(context,operation):
	s=bpy.context.scene
	o=operation
	getBounds(o)
	
	
	###########cutout strategy is completely here:
	if o.strategy=='CUTOUT':
		#ob=bpy.context.active_object
		offset=True
		if o.cut_type=='ONLINE' and o.onlycurves==True:#is separate to allow open curves :)
			print('separe')
			chunksFromCurve=[]
			for ob in o.objects:
				chunksFromCurve.extend(curveToChunks(ob))
			p=Polygon.Polygon()	
			for ch in chunksFromCurve:
				#print(ch.points)
				
				if len(ch.points)>2:
					ch.poly=chunkToPoly(ch)
					#p.addContour(ch.poly)
		else:
			chunksFromCurve=[]
			if o.cut_type=='ONLINE':
				p=getObjectOutline(0,o,True)
				
			else:
				offset=True
				if o.cut_type=='INSIDE':
					offset=False
				p=getObjectOutline(o.cutter_diameter/2,o,offset)
				if o.outlines_count>1:
					for i in range(1,o.outlines_count):
						chunksFromCurve.extend(polyToChunks(p,-1))
						p=outlinePoly(p,o.dist_between_paths,o.circle_detail,o.optimize,o.optimize_threshold,offset)
				
					
			chunksFromCurve.extend(polyToChunks(p,-1))
		
		#parentChildPoly(chunksFromCurve,chunksFromCurve,o)
		chunksFromCurve=limitChunks(chunksFromCurve,o)
		parentChildPoly(chunksFromCurve,chunksFromCurve,o)
		if o.outlines_count==1:
			chunksFromCurve=sortChunks(chunksFromCurve,o)
		
		#if o.outlines_count>0 and o.cut_type!='ONLINE' and o.movement_insideout=='OUTSIDEIN':#reversing just with more outlines
		#	chunksFromCurve.reverse()
						
		if (o.movement_type=='CLIMB' and o.spindle_rotation_direction=='CCW') or (o.movement_type=='CONVENTIONAL' and o.spindle_rotation_direction=='CW'):
			for ch in chunksFromCurve:
				ch.points.reverse()
			
		if o.cut_type=='INSIDE':#there would bee too many conditions above, so for now it gets reversed once again when inside cutting.
			for ch in chunksFromCurve:
				ch.points.reverse()
				
		
		if o.use_layers:
			layers=[]
			n=math.ceil((o.maxz-o.min.z)/o.stepdown)
			layerstart=o.maxz
			for x in range(0,n):
				layerend=max(o.maxz-((x+1)*o.stepdown),o.min.z)
				if int(layerstart*10**8)!=int(layerend*10**8):#it was possible that with precise same end of operation, last layer was done 2x on exactly same level...
					layers.append([layerstart,layerend])
				layerstart=layerend
		else:
				layers=[[o.maxz,o.min.z]]
			
		print(layers)
		extendorder=[]
		if o.first_down:#each shape gets either cut all the way to bottom, or every shape gets cut 1 layer, then all again. has to create copies, because same chunks are worked with on more layers usually
			for chunk in chunksFromCurve:
				for layer in layers:
					extendorder.append([chunk.copy(),layer])
		else:
			for layer in layers:
				for chunk in chunksFromCurve:
					extendorder.append([chunk.copy(),layer])
		
		for chl in extendorder:#Set Z for all chunks
			chunk=chl[0]
			layer=chl[1]
			print(layer[1])
			chunk.setZ(layer[1])
		
		chunks=[]
		
		if o.use_bridges:#add bridges to chunks
			#bridges=getBridges(p,o)
			bridgeheight=min(0,o.min.z+o.bridges_height)
			for chl in extendorder:
				chunk=chl[0]
				layer=chl[1]
				if layer[1]<bridgeheight:
					addBridges(chunk,o,0)
				
		if o.ramp:#add ramps or simply add chunks
			for chl in extendorder:
				chunk=chl[0]
				layer=chl[1]
				if chunk.closed:
					chunks.append(chunk.rampContour(layer[0],layer[1],o))
				else:
					chunks.append(chunk.rampZigZag(layer[0],layer[1],o))
		else:
			for chl in extendorder:
				chunks.append(chl[0])
						
		

		if bpy.app.debug_value==0 or bpy.app.debug_value==1 or bpy.app.debug_value==3 or bpy.app.debug_value==2:# or bpy.app.debug_value==4:
			chunksToMesh(chunks,o)

	if o.strategy=='POCKET':	
		p=getObjectOutline(o.cutter_diameter/2,o,False)
		all=Polygon.Polygon(p)
		approxn=(min(o.max.x-o.min.x,o.max.y-o.min.y)/o.dist_between_paths)/2
		i=0
		chunks=[]
		chunksFromCurve=[]
		lastchunks=[]
		centers=None
		while len(p)>0:
			nchunks=polyToChunks(p,o.min.z)
			nchunks=limitChunks(nchunks,o)
			chunksFromCurve.extend(nchunks)
			parentChildDist(lastchunks,nchunks,o)
			lastchunks=nchunks
			
			pnew=outlinePoly(p,o.dist_between_paths,o.circle_detail,o.optimize,o.optimize_threshold,False)
			
			if o.dist_between_paths>o.cutter_diameter/2.0:#this mess under this IF condition is here ONLY because of the ability to have stepover> than cutter radius. Other CAM softwares don't allow this at all, maybe because of this mathematical problem and performance cost, but into soft materials, this is good to have.
				o.warnings=o.warnings+'Distance between paths larger\n	than cutter radius can result in uncut areas!\n '

				contours_before=len(p)
				
				if centers==None:
					centers=[]
					for ci in range(0,len(p)):
						centers.append(p.center(ci))
				contours_after=len(pnew)
				newcenters=[]
				
				do_test=False
				for ci in range(0,len(pnew)):
					newcenters.append(pnew.center(ci))
					
					if len(p)>ci:#comparing polygons to detect larger changes in shape
						#print(ci,len(p))
						bb1=p.boundingBox(ci)
						bb2=pnew.boundingBox(ci)
						d1=dist2d(newcenters[ci],centers[ci])
						d2=0
						for bbi in range(0,4):
							d2=max(d2,abs(bb2[bbi]-bb1[bbi]))
					
					if contours_after!=contours_before or d1>o.dist_between_paths or d2>o.dist_between_paths*2:
						do_test=True
						#print(contours_before,contours_after)
						
				if len(pnew)==0:
					do_test=True
				#print(contours_before,contours_after)
				
				if do_test:	
					print('testing')
					prest=outlinePoly(p,o.cutter_diameter/2.0,o.circle_detail,o.optimize,o.optimize_threshold,False)#this estimates if there was a rest on the last cut
					
					for ci in range(0,len(prest)):
						bbcontour=prest.boundingBox(ci)
						add=False
						#if len(pnew)>ci:
						d=0
						bb2=pnew.boundingBox()
						bb1=prest.boundingBox()
						for bbi in range(0,4):
							d=max(d,abs(bb2[bbi]-bb1[bbi]))
						if d>o.dist_between_paths*2:
							add=True
							#print('pnew boundbox vs restboundbox')
							#print(d/o.dist_between_paths)
						
						if min(bbcontour[1]-bbcontour[0],bbcontour[3]-bbcontour[2])<o.dist_between_paths*2:
							add=True
							#print('small rest boundbox')

						if add:
							#print('adding extra contour rest')
							#print(prest[ci])
							rest=Polygon.Polygon(prest[ci])
							nchunks=polyToChunks(rest,o.min.z)
							nchunks=limitChunks(nchunks,o)
							parentChildDist(lastchunks,nchunks,o)
							nchunks.extend(chunksFromCurve)#appending these to the beginning, so they get milled first.
							chunksFromCurve=nchunks
							
				centers=newcenters

			percent=int(i/approxn*100)
			progress('outlining polygons ',percent) 
			p=pnew
			
			i+=1
		
		if (o.movement_type=='CLIMB' and o.spindle_rotation_direction=='CW') or (o.movement_type=='CONVENTIONAL' and o.spindle_rotation_direction=='CCW'):
			for ch in chunksFromCurve:
				ch.points.reverse()
				
		#if bpy.app.debug_value==1:
		

		chunksFromCurve=sortChunks(chunksFromCurve,o)
			
		chunks=[]
		if o.use_layers:
			n=math.ceil((o.maxz-o.min.z)/o.stepdown)
			layers=[]
			layerstart=o.maxz
			for x in range(0,n):
				layerend=max(o.maxz-((x+1)*o.stepdown),o.min.z)
				layers.append([layerstart,layerend])
				layerstart=layerend
		else:
			layers=[[o.maxz,o.min.z]]

		#print(layers)
		#print(chunksFromCurve)
		#print(len(chunksFromCurve))
		for l in layers:
			lchunks=setChunksZ(chunksFromCurve,l[1])
			###########helix_enter first try here TODO: check if helix radius is not out of operation area.
			if o.helix_enter:
				helix_radius=o.cutter_diameter*0.5*o.helix_diameter*0.01#90 percent of cutter radius
				helix_circumference=helix_radius*pi*2
				
				revheight=helix_circumference*tan(o.ramp_in_angle)
				for chi,ch in enumerate(lchunks):
					if chunksFromCurve[chi].children==[]:
					
						p=ch.points[0]#TODO:intercept closest next point when it should stay low 
						#first thing to do is to check if helix enter can really enter.
						checkc=Circle(helix_radius+o.cutter_diameter/2,o.circle_detail)
						checkc.shift(p[0],p[1])
						covers=False
						for poly in o.silhouete:
							if poly.covers(checkc):
								covers=True
								break;
						
						if covers:
							revolutions=(l[0]-p[2])/revheight
							#print(revolutions)
							h=Helix(helix_radius,o.circle_detail, l[0],p,revolutions)
							#invert helix if not the typical direction
							if (o.movement_type=='CONVENTIONAL' and o.spindle_rotation_direction=='CW') or (o.movement_type=='CLIMB'	and o.spindle_rotation_direction=='CCW'):
								nhelix=[]
								for v in h:
									nhelix.append((2*p[0]-v[0],v[1],v[2]))
								h=nhelix
							ch.points=h+ch.points
						else:
							o.warnings=o.warnings+'Helix entry did not fit! \n '
							ch.closed=True
							lchunks[chi]=ch.rampZigZag(l[0],l[1],o)
			#Arc retract here first try:
			if o.retract_tangential:#TODO: check for entry and exit point before actual computing... will be much better.
									#TODO: fix this for CW and CCW!
				for chi, ch in enumerate(lchunks):
					#print(chunksFromCurve[chi])
					#print(chunksFromCurve[chi].parents)
					if chunksFromCurve[chi].parents==[] or len(chunksFromCurve[chi].parents)==1:
						
						revolutions=0.25
						v1=Vector(ch.points[-1])
						i=-2
						v2=Vector(ch.points[i])
						v=v1-v2
						while v.length==0:
							i=i-1
							v2=Vector(ch.points[i])
							v=v1-v2
						
						v.normalize()
						rotangle=Vector((v.x,v.y)).angle_signed(Vector((1,0)))
						e=Euler((0,0,pi/2.0))# TODO:#CW CLIMB!
						v.rotate(e)
						p=v1+v*o.retract_radius
						center = p
						p=(p.x,p.y,p.z)
						
						#progress(str((v1,v,p)))
						h=Helix(o.retract_radius, o.circle_detail, p[2]+o.retract_height,p, revolutions)
						
						e=Euler((0,0,rotangle+pi))#angle to rotate whole retract move
						rothelix=[]
						c=[]#polygon for outlining and checking collisions.
						for p in h:#rotate helix to go from tangent of vector
							v1=Vector(p)
							
							v=v1-center
							v.x=-v.x#flip it here first...
							v.rotate(e)
							p=center+v
							rothelix.append(p)
							c.append((p[0],p[1]))
							
						c=Polygon.Polygon(c)
						#print('çoutline')
						#print(c)
						coutline = outlinePoly(c,o.cutter_diameter/2,o.circle_detail,o.optimize,o.optimize_threshold,offset = True)
						#print(h)
						#print('çoutline')
						#print(coutline)
						#polyToMesh(coutline,0)
						rothelix.reverse()
						
						covers=False
						for poly in o.silhouete:
							if poly.covers(coutline):
								covers=True
								break;
						
						if covers:
							ch.points.extend(rothelix)
			chunks.extend(lchunks)
		
		chunksToMesh(chunks,o)
		
	elif o.strategy=='CURVE':
		pathSamples=[]
		ob=bpy.data.objects[o.curve_object]
		pathSamples.extend(curveToChunks(ob))
		pathSamples=sortChunks(pathSamples,o)#sort before sampling
		pathSamples=chunksRefine(pathSamples,o)
		chunksToMesh(pathSamples,o)
		
	elif o.strategy=='PARALLEL' or o.strategy=='CROSS' or o.strategy=='BLOCK' or o.strategy=='SPIRAL' or o.strategy=='CIRCLES' or o.strategy=='OUTLINEFILL' or o.strategy=='CARVE'or o.strategy=='PENCIL' or o.strategy=='CRAZY':  
		
		if o.strategy=='CARVE':
			pathSamples=[]
			#for ob in o.objects:
			ob=bpy.data.objects[o.curve_object]
			pathSamples.extend(curveToChunks(ob))
			pathSamples=sortChunks(pathSamples,o)#sort before sampling
			pathSamples=chunksRefine(pathSamples,o)
		elif o.strategy=='PENCIL':
			prepareArea(o)
			getAmbient(o)
			pathSamples=getOffsetImageCavities(o,o.offset_image)
			#for ch in pathSamples:
			#	for i,p in enumerate(ch.points):
			#	 ch.points[i]=(p[0],p[1],0)
			pathSamples=limitChunks(pathSamples,o)
			pathSamples=sortChunks(pathSamples,o)#sort before sampling
		elif o.strategy=='CRAZY':
			prepareArea(o)
			
			pathSamples = crazyStrokeImage(o)
			#####this kind of worked and should work:
			#area=o.offset_image>o.min.z
			#pathSamples = crazyStrokeImageBinary(o,area)
			#####
			pathSamples=chunksRefine(pathSamples,o)
			#pathSamples = sortChunks(pathSamples,o)
		else: 
			if o.strategy=='OUTLINEFILL':
				getOperationSilhouete(o)
			pathSamples=getPathPattern(o)
			#chunksToMesh(pathSamples,o)#for testing pattern script
			#return
			if o.strategy=='OUTLINEFILL':
				pathSamples=sortChunks(pathSamples,o)

		#print (minz)
		
		
		chunks=[]
		if o.use_layers:
			n=math.ceil((o.maxz-o.min.z)/o.stepdown)
			layers=[]
			for x in range(0,n):
				
				layerstart=o.maxz-(x*o.stepdown)
				layerend=max(o.maxz-((x+1)*o.stepdown),o.min.z)
				layers.append([layerstart,layerend])
				
				
		else:
			layerstart=o.maxz#
			layerend=o.min.z#
			layers=[[layerstart,layerend]]
		
		
		chunks.extend(sampleChunks(o,pathSamples,layers))
		if (o.strategy=='PENCIL'):# and bpy.app.debug_value==-3:
			chunks=chunksCoherency(chunks)
			print('coherency check')
			
		if ((o.strategy=='PARALLEL' or o.strategy=='CROSS') or o.strategy=='PENCIL'):# and not o.parallel_step_back:
			chunks=sortChunks(chunks,o)
		if o.ramp:
			for ch in chunks:
				nchunk = ch.rampZigZag(ch.zstart, ch.points[0][2],o)
				ch.points=nchunk.points
		#print(chunks)
		if o.strategy=='CARVE':
			for ch in chunks:
				for vi in range(0,len(ch.points)):
					ch.points[vi]=(ch.points[vi][0],ch.points[vi][1],ch.points[vi][2]-o.carve_depth)
	
		chunksToMesh(chunks,o)
		
		
	elif o.strategy=='WATERLINE':
		topdown=True
		tw=time.time()
		chunks=[]
		progress ('retrieving object slices')
		prepareArea(o)
		layerstep=1000000000
		if o.use_layers:
			layerstep=math.floor(o.stepdown/o.slice_detail)
			if layerstep==0:
				layerstep=1
				
		#for projection of filled areas	 
		layerstart=0#
		layerend=o.min.z#
		layers=[[layerstart,layerend]]
		#######################	 
		nslices=ceil(abs(o.minz/o.slice_detail))
		lastislice=numpy.array([])
		lastslice=Polygon.Polygon()#polyversion
		layerstepinc=0
		
		slicesfilled=0
		getAmbient(o)
		#polyToMesh(o.ambient,0)
		for h in range(0,nslices):
			layerstepinc+=1
			slicechunks=[]
			z=o.minz+h*o.slice_detail
			#print(z)
			#sliceimage=o.offset_image>z
			islice=o.offset_image>z
			slicepolys=imageToPoly(o,islice,with_border=True)
			#for pviz in slicepolys:
			#	polyToMesh('slice',pviz,z)
			poly=Polygon.Polygon()#polygversion
			lastchunks=[]
			#imagechunks=imageToChunks(o,islice)
			#for ch in imagechunks:
			#	slicechunks.append(camPathChunk([]))
			#	for s in ch.points:
			#	 slicechunks[-1].points.append((s[0],s[1],z))
					
			
			#print('found polys',layerstepinc,len(slicepolys))
			for p in slicepolys:
				#print('polypoints',p.nPoints(0))
				poly+=p#polygversion TODO: why is this added?
				#print()
				#polyToMesh(p,z)
				nchunks=polyToChunks(p,z)
				nchunks=limitChunks(nchunks,o, force=True)
				#print('chunksnum',len(nchunks))
				#if len(nchunks)>0:
				#	print('chunkpoints',len(nchunks[0].points))
				#print()
				lastchunks.extend(nchunks)
				slicechunks.extend(nchunks)
				#print('totchunks',len(slicechunks))
			if len(slicepolys)>0:
				slicesfilled+=1
				#chunks.extend(polyToChunks(slicepolys[1],z))
				#print(len(p),'slicelen')
			
			
			#
			#print(len(lastslice))
			#'''
			if o.waterline_fill:
				layerstart=min(o.maxz,z+o.slice_detail)#
				layerend=max(o.min.z,z-o.slice_detail)#
				layers=[[layerstart,layerend]]
				#####################################
				#fill top slice for normal and first for inverse, fill between polys
				if len(lastslice)>0 or (o.inverse and len(poly)>0 and slicesfilled==1):
					offs=False
					if len(lastslice)>0:#between polys
						if o.inverse:
							restpoly=poly-lastslice
						else:
							restpoly=lastslice-poly#Polygon.Polygon(lastslice)
						#print('filling between')
					if (not o.inverse and len(poly)==0 and slicesfilled>0) or (o.inverse and len(poly)>0 and slicesfilled==1):#first slice fill
						restpoly=lastslice
						#print('filling first')
					
					#print(len(restpoly))
					#polyToMesh('fillrest',restpoly,z)
					restpoly=outlinePoly(restpoly,o.dist_between_paths,o.circle_detail,o.optimize,o.optimize_threshold,offs)
					fillz = z 
					i=0
					while len(restpoly)>0:
						nchunks=polyToChunks(restpoly,fillz)
						#project paths TODO: path projection during waterline is not working
						if o.waterline_project:
							nchunks=chunksRefine(nchunks,o)
							nchunks=sampleChunks(o,nchunks,layers)
							
						nchunks=limitChunks(nchunks,o, force=True)
						#########################
						slicechunks.extend(nchunks)
						parentChildDist(lastchunks,nchunks,o)
						lastchunks=nchunks
						#slicechunks.extend(polyToChunks(restpoly,z))
						restpoly=outlinePoly(restpoly,o.dist_between_paths,o.circle_detail,o.optimize,o.optimize_threshold,offs)
						i+=1
						#print(i)
				i=0
				#'''
				#####################################
				# fill layers and last slice, last slice with inverse is not working yet - inverse millings end now always on 0 so filling ambient does have no sense.
				if (slicesfilled>0 and layerstepinc==layerstep) or (not o.inverse and len(poly)>0 and slicesfilled==1) or (o.inverse and len(poly)==0 and slicesfilled>0):
					fillz=z
					layerstepinc=0
					
					#ilim=1000#TODO:this should be replaced... no limit, just check if the shape grows over limits.
					
					offs=False
					boundrect=o.ambient#Polygon.Polygon(((o.min.x,o.min.y),(o.min.x,o.max.y),(o.max.x,o.max.y),(o.max.x,o.min.y)))
					
					restpoly=boundrect-poly
					if (o.inverse and len(poly)==0 and slicesfilled>0):
						restpoly=boundrect-lastslice
					
					restpoly=outlinePoly(restpoly,o.dist_between_paths,o.circle_detail,o.optimize,o.optimize_threshold,offs)
					i=0
					while len(restpoly)>0:
						print(i)
						nchunks=polyToChunks(restpoly,fillz)
						#########################
						nchunks=limitChunks(nchunks,o, force=True)
						slicechunks.extend(nchunks)
						parentChildDist(lastchunks,nchunks,o)
						lastchunks=nchunks
						#slicechunks.extend(polyToChunks(restpoly,z))
						restpoly=outlinePoly(restpoly,o.dist_between_paths,o.circle_detail,o.optimize,o.optimize_threshold,offs)
						i+=1
				
				
				#'''
				percent=int(h/nslices*100)
				progress('waterline layers ',percent)  
				lastslice=poly
				
			#print(poly)
			#print(len(lastslice))
			'''
			if len(lastislice)>0:
				i=numpy.logical_xor(lastislice , islice)
				
				n=0
				while i.sum()>0 and n<10000:
					i=outlineImageBinary(o,o.dist_between_paths,i,False)
					polys=imageToPoly(o,i)
					for poly in polys:
						chunks.extend(polyToChunks(poly,z))
					n+=1
			
		
					#restpoly=outlinePoly(restpoly,o.dist_between_paths,oo.circle_detail,o.optimize,o.optimize_threshold,,False)
					#chunks.extend(polyToChunks(restpoly,z))
					
			lastislice=islice
			'''
			
			
			#if bpy.app.debug_value==1:
			if (o.movement_type=='CONVENTIONAL' and o.spindle_rotation_direction=='CCW') or (o.movement_type=='CLIMB' and o.		spindle_rotation_direction=='CW'):
				for chunk in slicechunks:
					chunk.points.reverse()
			slicechunks=sortChunks(slicechunks,o)
			if topdown:
				slicechunks.reverse()
			#project chunks in between
			
			chunks.extend(slicechunks)
		#chunks=sortChunks(chunks)
		if topdown:
			chunks.reverse()
			'''
			chi=0
			if len(chunks)>2:
				while chi<len(chunks)-2:
					d=dist2d((chunks[chi][-1][0],chunks[chi][-1][1]),(chunks[chi+1][0][0],chunks[chi+1][0][1]))
					if chunks[chi][0][2]>=chunks[chi+1][0][2] and d<o.dist_between_paths*2:
						chunks[chi].extend(chunks[chi+1])
						chunks.remove(chunks[chi+1])
						chi=chi-1
					chi+=1
			'''
		print(time.time()-tw)
		chunksToMesh(chunks,o)	
		
	elif o.strategy=='DRILL':
		chunks=[]
		for ob in o.objects:
			activate(ob)
		
			bpy.ops.object.duplicate_move(OBJECT_OT_duplicate={"linked":False, "mode":'TRANSLATION'}, TRANSFORM_OT_translate={"value":(0, 0, 0), "constraint_axis":(False, False, False), "constraint_orientation":'GLOBAL', "mirror":False, "proportional":'DISABLED', "proportional_edit_falloff":'SMOOTH', "proportional_size":1, "snap":False, "snap_target":'CLOSEST', "snap_point":(0, 0, 0), "snap_align":False, "snap_normal":(0, 0, 0), "texture_space":False, "release_confirm":False})
			bpy.ops.group.objects_remove_all()
			ob=bpy.context.active_object
			ob.data.dimensions='3D'
			try:
				bpy.ops.object.transform_apply(location=True, rotation=False, scale=False)
				bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
				bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
				
			except:
				pass
			l=ob.location
			
			if ob.type=='CURVE':
				
				for c in ob.data.splines:
						maxx,minx,maxy,miny=-10000,10000,-10000,100000
						for p in c.points:
							if o.drill_type=='ALL_POINTS':
								chunks.append(camPathChunk([(p.co.x+l.x,p.co.y+l.y,o.min.z)]))
							minx=min(p.co.x,minx)
							maxx=max(p.co.x,maxx)
							miny=min(p.co.y,miny)
							maxy=max(p.co.y,maxy)
						for p in c.bezier_points:
							if o.drill_type=='ALL_POINTS':
								chunks.append(camPathChunk([(p.co.x+l.x,p.co.y+l.y,o.min.z)]))
							minx=min(p.co.x,minx)
							maxx=max(p.co.x,maxx)
							miny=min(p.co.y,miny)
							maxy=max(p.co.y,maxy)
						cx=(maxx+minx)/2
						cy=(maxy+miny)/2
						
						center=(cx,cy)
						aspect=(maxx-minx)/(maxy-miny)
						if (1.3>aspect>0.7 and o.drill_type=='MIDDLE_SYMETRIC') or o.drill_type=='MIDDLE_ALL': 
							chunks.append(camPathChunk([(center[0]+l.x,center[1]+l.y,o.min.z)]))
						
			delob(ob)#delete temporary object with applied transforms
		print(chunks)
		chunks=sortChunks(chunks,o)
		print(chunks)
		chunksToMesh(chunks,o)
	elif o.strategy=='MEDIAL_AXIS':
		print('doing highly experimental stuff')
		
		from cam.voronoi import Site, computeVoronoiDiagram
		
		chunksFromCurve=[]
		
		gpoly=Polygon.Polygon()	
		for ob in o.objects:
			polys=getOperationSilhouete(o)
			for poly in polys:
				chunks=polyToChunks(poly,-1)
				chunks = chunksRefine(chunks,o)
				
				'''
				chunksFromCurve.extend(polyToChunks(p,-1))
			
				for i,c in enumerate(p):
					gp.addContour(c,p.isHole(i))
					
			
			chunksFromCurve = chunksRefine(chunksFromCurve,o)
			
			
					
			points=[]
			for ch in chunksFromCurve:		
				for pt in ch.points:
					pvoro = Site(pt[0], pt[1])
					points.append(pt)#(pt[0], pt[1]), pt[2])
				'''
				verts=[]
				for ch in chunks:		
					for pt in ch.points:
						#pvoro = Site(pt[0], pt[1])
						verts.append(pt)#(pt[0], pt[1]), pt[2])
				#verts= points#[[vert.x, vert.y, vert.z] for vert in vertsPts]
				nDupli,nZcolinear = unique(verts)
				nVerts=len(verts)
				print(str(nDupli)+" duplicates points ignored")
				print(str(nZcolinear)+" z colinear points excluded")
				if nVerts < 3:
					self.report({'ERROR'}, "Not enough points")
					return {'FINISHED'}
				#Check colinear
				xValues=[pt[0] for pt in verts]
				yValues=[pt[1] for pt in verts]
				if checkEqual(xValues) or checkEqual(yValues):
					self.report({'ERROR'}, "Points are colinear")
					return {'FINISHED'}
				#Create diagram
				print("Tesselation... ("+str(nVerts)+" points)")
				xbuff, ybuff = 5, 5 # %
				zPosition=0
				vertsPts= [Point(vert[0], vert[1], vert[2]) for vert in verts]
				#vertsPts= [Point(vert[0], vert[1]) for vert in verts]
				
				pts, edgesIdx = computeVoronoiDiagram(vertsPts, xbuff, ybuff, polygonsOutput=False, formatOutput=True)
				
				#
				pts=[[pt[0], pt[1], zPosition] for pt in pts]
				newIdx=0
				vertr=[]
				filteredPts=[]
				print('filter points')
				for p in pts:
					if not poly.isInside(p[0],p[1]):
						vertr.append((True,-1))
					else:
						vertr.append((False,newIdx))
						filteredPts.append(p)
						newIdx+=1
						
				print('filter edges')		
				filteredEdgs=[]
				for e in edgesIdx:
					
					do=True
					p1=pts[e[0]]
					p2=pts[e[1]]
					#print(p1,p2,len(vertr))
					if vertr[e[0]][0]:
						do=False
					elif vertr[e[1]][0]:
						do=False
					if do:
						filteredEdgs.append(((vertr[e[0]][1],vertr[e[1]][1])))
				
				#segments=[]
				#processEdges=filteredEdgs.copy()
				#chunk=camPathChunk([])
				#chunk.points.append(filteredEdgs.pop())
				#while len(filteredEdgs)>0:
					
				#Create new mesh structure
				
				print("Create mesh...")
				voronoiDiagram = bpy.data.meshes.new("VoronoiDiagram") #create a new mesh
				
				
						
				voronoiDiagram.from_pydata(filteredPts, filteredEdgs, []) #Fill the mesh with triangles
				
				voronoiDiagram.update(calc_edges=True) #Update mesh with new data
				#create an object with that mesh
				voronoiObj = bpy.data.objects.new("VoronoiDiagram", voronoiDiagram)
				#place object
				#bpy.ops.view3d.snap_cursor_to_selected()#move 3d-cursor
				
				#update scene
				bpy.context.scene.objects.link(voronoiObj) #Link object to scene
				bpy.context.scene.objects.active = voronoiObj
				voronoiObj.select = True
				

				#bpy.ops.object.convert(target='CURVE')
		bpy.ops.object.join()
	''''
	pt_list = []
	x_max = obj[0][0]
	x_min = obj[0][0]
	y_min = obj[0][1]
	y_max = obj[0][1]
	# creates points in format for voronoi library, throwing away z
	for pt in obj:
		x, y = pt[0], pt[1]
		x_max = max(x, x_max)
		x_min = min(x, x_min)
		y_max = max(y, y_max)
		y_min = min(x, x_min)
		pt_list.append(Site(pt[0], pt[1]))

	res = computeVoronoiDiagram(pt_list)

	edges = res[2]
	delta = self.clip
	x_max = x_max + delta
	y_max = y_max + delta

	x_min = x_min - delta
	y_min = y_min - delta

	# clipping box to bounding box.
	pts_tmp = []
	for pt in res[0]:
		x, y = pt[0], pt[1]
		if x < x_min:
			x = x_min
		if x > x_max:
			x = x_max

		if y < y_min:
			y = y_min
		if y > y_max:
			y = y_max
		pts_tmp.append((x, y, 0))

	pts_out.append(pts_tmp)

	edges_out.append([(edge[1], edge[2]) for edge in edges if -1 not in edge])

	'''
		
	#progress('finished')
	
#tools for voroni graphs all copied from the delaunayVoronoi addon:
class Point:
	def __init__(self, x, y, z):
		self.x, self.y, self.z= x, y, z

def unique(L):
	"""Return a list of unhashable elements in s, but without duplicates.
	[[1, 2], [2, 3], [1, 2]] >>> [[1, 2], [2, 3]]"""
	#For unhashable objects, you can sort the sequence and then scan from the end of the list, deleting duplicates as you go
	nDupli=0
	nZcolinear=0
	L.sort()#sort() brings the equal elements together; then duplicates are easy to weed out in a single pass.
	last = L[-1]
	for i in range(len(L)-2, -1, -1):
		if last[:2] == L[i][:2]:#XY coordinates compararison
			if last[2] == L[i][2]:#Z coordinates compararison
				nDupli+=1#duplicates vertices
			else:#Z colinear
				nZcolinear+=1
			del L[i]
		else:
			last = L[i]
	return (nDupli,nZcolinear)#list data type is mutable, input list will automatically update and doesn't need to be returned

def checkEqual(lst):
	return lst[1:] == lst[:-1]	
	
def getPath4axis(context,operation):
	t=time.clock()
	s=bpy.context.scene
	o=operation
	getBounds(o)
	if o.strategy4axis=='PARALLELA' or o.strategy4axis=='PARALLELX':  
		pathSamples=getPathPattern4axis(o)
		
		depth=pathSamples[0].depth
		chunks=[]
		
		if o.use_layers:
			n=math.ceil(-(depth/o.stepdown))
			layers=[]
			for x in range(0,n):
				
				layerstart=-(x*o.stepdown)
				layerend=max(-((x+1)*o.stepdown),depth)
				layers.append([layerstart,layerend])
		else:
			layerstart=0#
			layerend=depth#
			layers=[[layerstart,layerend]]
		
		chunks.extend(sampleChunksNAxis(o,pathSamples,layers))
		chunksToMesh(chunks,o)

def prepare5axisIndexed(o):
	s=bpy.context.scene
	#first store objects positions/rotations
	o.matrices=[]
	for ob in o.objects:
		o.matrices.append(ob.matrix_world)
	#then rotate them
	for ob in o.objects:
		ob.select=True
		
	s.cursor_location=(0,0,0)
	oriname=o.name+' orientation'
	ori=s.objects[oriname]
	
	rot=ori.matrix_world.inverted()
	#rot.x=-rot.x
	#rot.y=-rot.y
	#rot.z=-rot.z
	rotationaxes = rotTo2axes(ori.rotation_euler,'CA')
	
	#bpy.context.space_data.pivot_point = 'CURSOR'
	#bpy.context.space_data.pivot_point = 'CURSOR'

	for ob in o.objects:
		
		ob.rotation_euler.rotate(rot)

def cleanup5axisIndexed(operation):
	for i,ob in enumerate(o.objects):
		ob.matrix_world=o.matrices[i]
		
def rotTo2axes(e,axescombination):
	'''converts an orientation object rotation to rotation defined by 2 rotational axes.
	attempting to do this for all axes combinations.
	'''
	v=Vector((0,0,1))
	v.rotate(e)
	if axescombination=='CA':
		v2d=Vector((v.x,v.y))
		a1base=Vector((0,1))#?is this right?It should be vector defining 0 rotation
		if v2d.length>0:
			cangle=a1base.angle_signed(v2d)
		else:
			return(0,0)
		v2d=Vector((v2d.length,v.z))
		a2base=Vector((0,1))
		aangle=a2base.angle_signed(v2d)
		print(cangle,aangle)
		return (cangle,aangle)
	elif axescombination=='CB':
		v2d=Vector((v.x,v.y))
		a1base=Vector((1,0))#?is this right?It should be vector defining 0 rotation
		if v2d.length>0:
			cangle=a1base.angle_signed(v2d)
		else:
			return(0,0)
		v2d=Vector((v2d.length,v.z))
		a2base=Vector((0,1))
		bangle=a2base.angle_signed(v2d)
		print(cangle,bangle)
		return (cangle,bangle)

	'''
	v2d=((v[a[0]],v[a[1]]))
	angle1=a1base.angle(v2d)#C for ca
	print(angle1)
	if axescombination[0]=='C':
		e1=Vector((0,0,-angle1))
	elif axescombination[0]=='A':#TODO: finish this after prototyping stage
		pass;
	v.rotate(e1)
	vbase=Vector(0,1,0)
	bangle=v.angle(vzbase)
	print(v)
	print(bangle)
	'''
	return(angle1,angle2)
	
def getPath(context,operation):#should do all path calculations.
	t=time.clock()

	if operation.axes=='3':
		getPath3axis(context,operation)
	elif operation.axes=='4':
		getPath4axis(context,operation)
	elif operation.axes=='5':#5 axis operations are now only 3 axis operations that get rotated...
		operation.orientation = prepare5axisIndexed(operation)
		getPath3axis(context,operation)
		cleanup5axisIndexed(operation)
		pass
	t1=time.clock()-t 
	progress('total time',t1)

def reload_paths(o):
	oname = "cam_path_"+o.name
	s=bpy.context.scene
	#for o in s.objects:
	ob=None
	if oname in s.objects:
		s.objects[oname].data.name='xxx_cam_deleted_path'
		ob=s.objects[oname]
	
	picklepath=getCachePath(o)+'.pickle'
	f=open(picklepath,'rb')
	d=pickle.load(f)
	f.close()
	'''
	passed=False
	while not passed:
		try:
			f=open(picklepath,'rb')
			d=pickle.load(f)
			f.close()
			passed=True
		except:
			print('sleep')
			time.sleep(1)
	'''
	o.warnings=d['warnings']
	o.duration=d['duration']
	verts=d['path']
	
	edges=[]
	for a in range(0,len(verts)-1):
		edges.append((a,a+1))
		
	oname="cam_path_"+o.name
	mesh = bpy.data.meshes.new(oname)
	mesh.name=oname
	mesh.from_pydata(verts, edges, [])
	
	if oname in s.objects:
		s.objects[oname].data=mesh
	else: 
		object_utils.object_data_add(bpy.context, mesh, operator=None)
		ob=bpy.context.active_object
		ob.name=oname
	ob=s.objects[oname]
	ob.location=(0,0,0)
	o.path_object_name=oname
	o.changed=False
	#unpickle here:
	

	
