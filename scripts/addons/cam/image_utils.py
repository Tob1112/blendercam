import numpy
import math
import time
import random

import curve_simplify
import mathutils
from mathutils import *

from cam import simple
from cam.simple import *
from cam import chunk
from cam.chunk import *

def getCircle(r,z):
	car=numpy.array((0),dtype=float)
	res=2*r
	m=r
	car.resize(r*2,r*2)
	car.fill(-10)
	v=mathutils.Vector((0,0,0))
	for a in range(0,res):
		v.x=(a+0.5-m)
		for b in range(0,res):
			v.y=(b+0.5-m)
			if(v.length<=r):
				car[a,b]=z
	return car

def getCircleBinary(r):
	car=numpy.array((False),dtype=bool)
	res=2*r
	m=r
	car.resize(r*2,r*2)
	car.fill(False)
	v=mathutils.Vector((0,0,0))
	for a in range(0,res):
		v.x=(a+0.5-m)
		for b in range(0,res):
			v.y=(b+0.5-m)
			if(v.length<=r):
				car.itemset((a,b),True)
	return car

# get cutters for the z-buffer image method
def getCutterArray(operation,pixsize):
	type=operation.cutter_type
	#print('generating cutter')
	r=operation.cutter_diameter/2+operation.skin#/operation.pixsize
	res=ceil((r*2)/pixsize)
	#if res%2==0:#compensation for half-pixels issue, which wasn't an issue, so commented out
		#res+=1
		#m=res/2
	m=res/2.0
	car=numpy.array((0),dtype=float)
	car.resize(res,res)
	car.fill(-10)
	
	v=mathutils.Vector((0,0,0))
	ps=pixsize
	if type=='END':
		for a in range(0,res):
			v.x=(a+0.5-m)*ps
			for b in range(0,res):
				v.y=(b+0.5-m)*ps
				if(v.length<=r):
					car.itemset((a,b),0)
	elif type=='BALL':
		for a in range(0,res):
			v.x=(a+0.5-m)*ps
			for b in range(0,res):
				v.y=(b+0.5-m)*ps
				if(v.length<=r):
					z=sin(acos(v.length/r))*r-r
					car.itemset((a,b),z)#[a,b]=z
				
	elif type=='VCARVE' :
		angle=operation.cutter_tip_angle 
		s=math.tan(math.pi*(90-angle/2)/180)
		for a in range(0,res):
			v.x=(a+0.5-m)*ps
			for b in range(0,res):
				v.y=(b+0.5-m)*ps
				if v.length<=r:
					z=(-v.length*s)
					car.itemset((a,b),z)
	elif type=='CUSTOM':
		cutob=bpy.data.objects[operation.cutter_object_name]
		scale = ((cutob.dimensions.x/cutob.scale.x)/2)/r#
		#print(cutob.scale)
		vstart=Vector((0,0,-10))
		vend=Vector((0,0,10))
		print('sampling custom cutter')
		maxz=-1
		for a in range(0,res):
			vstart.x=(a+0.5-m)*ps*scale
			vend.x=vstart.x
			
			for b in range(0,res):
				vstart.y=(b+0.5-m)*ps*scale
				vend.y=vstart.y
				
				c=cutob.ray_cast(vstart,vend)
				if c[2]!=-1:
					z=-c[0][2]/scale
					#print(c)
					if z>-9:
						#print(z)
						if z>maxz:
							maxz=z
						car.itemset((a,b),z)
		car-=maxz
	return car
				
def numpysave(a,iname):
	inamebase=bpy.path.basename(iname)

	i=numpytoimage(a,inamebase)
	
	r=bpy.context.scene.render
	
	r.image_settings.file_format='OPEN_EXR'
	r.image_settings.color_mode='BW'
	r.image_settings.color_depth='32'
	
	i.save_render(iname)

def numpytoimage(a,iname):
	t=time.time()
	print('numpy to image')
	t=time.time()
	print(a.shape[0],a.shape[1])
	foundimage=False
	for image in bpy.data.images:
		
		if image.name[:len(iname)]==iname and image.size[0]==a.shape[0] and image.size[1]==a.shape[1]:
			i=image
			foundimage=True
	if not foundimage:
		bpy.ops.image.new(name=iname, width=a.shape[0], height=a.shape[1], color=(0, 0, 0, 1), alpha=True, generated_type='BLANK', float=True)
		for image in bpy.data.images:
			
			if image.name[:len(iname)]==iname and image.size[0]==a.shape[0] and image.size[1]==a.shape[1]:
				i=image
			
	d=a.shape[0]*a.shape[1]
	a=a.swapaxes(0,1)
	a=a.reshape(d)
	a=a.repeat(4)
	a[3::4]=1
	#i.pixels=a this was 50 percent slower...
	i.pixels[:]=a[:]#this gives big speedup!	
	print('\ntime '+str(time.time()-t))
	return i


def imagetonumpy(i):
	t=time.time()
	inc=0
	
	width=i.size[0]
	height=i.size[1]
	x=0
	y=0
	count=0
	na=numpy.array((0.1),dtype=float)
	
	size=width*height
	na.resize(size*4)		
	
	p=i.pixels[:]#these 2 lines are about 15% faster than na=i.pixels[:].... whyyyyyyyy!!?!?!?!?! Blender image data access is evil.
	na[:]=p
	#na=numpy.array(i.pixels[:])#this was terribly slow... at least I know why now, it probably 
	na=na[::4]
	na=na.reshape(height,width)
	na=na.swapaxes(0,1)
	
	print('\ntime of image to numpy '+str(time.time()-t))	
	return na

def offsetArea(o,samples):
	if o.update_offsetimage_tag:
		minx,miny,minz,maxx,maxy,maxz=o.min.x,o.min.y,o.min.z,o.max.x,o.max.y,o.max.z
		o.offset_image.fill(-10)
		
		sourceArray=samples
		cutterArray=getCutterArray(o,o.pixsize)
		
		#progress('image size', sourceArray.shape)
		
		width=len(sourceArray)
		height=len(sourceArray[0])
		cwidth=len(cutterArray)
		
		t=time.time()
	
		m=int(cwidth/2.0)
		
		
		
		if o.inverse:
			sourceArray=-sourceArray+minz
			
		comparearea=o.offset_image[m: width-cwidth+m, m:height-cwidth+m]
		#i=0  
		for x in range(0,cwidth):#cwidth):
			text="Offsetting depth "+str(int(x*100/cwidth))
			#o.operator.report({"INFO"}, text)
			progress('offset ',int(x*100/cwidth))
			for y in range(0,cwidth):#TODO:OPTIMIZE THIS - this can run much faster when the areas won't be created each run????tests dont work now
				if cutterArray[x,y]>-10:
					#i+=1
					#progress(i)
					comparearea=numpy.maximum(sourceArray[  x : width-cwidth+x ,y : height-cwidth+y]+cutterArray[x,y],comparearea)
		
		o.offset_image[m: width-cwidth+m, m:height-cwidth+m]=comparearea
		#progress('offseting done')
		
		progress('\ntime '+str(time.time()-t))
		
		o.update_offsetimage_tag=False
		#progress('doing offsetimage')
		#numpytoimage(o.offset_image,o)
	return o.offset_image

def outlineImageBinary(o,radius,i,offset):
	t=time.time()
	progress('outline image')
	r=ceil(radius/o.pixsize)
	c=getCircleBinary(r)
	w=len(i)
	h=len(i[0])
	oar=i.copy()
	#oar.fill(-10000000)
	
	ar = i[:,:-1] != i[:,1:] 
	indices1=ar.nonzero()
	if offset:
		dofunc=numpy.logical_or
	else:
		c=numpy.logical_not(c)
		dofunc=numpy.logical_and
	w=i.shape[0]
	h=i.shape[1]
	for id in range(0,len(indices1[0])):
		a=indices1[0].item(id)
		b=indices1[1].item(id)
		if a>r and b>r and a<w-r and b<h-r:
			#progress(oar.shape,c.shape)
			oar[a-r:a+r,b-r:b+r]=dofunc(oar[a-r:a+r,b-r:b+r],c)
		
	ar=i[:-1,:]!=i[1:,:]
	indices2=ar.nonzero()
	for id in range(0,len(indices2[0])):
		a=indices2[0].item(id)
		b=indices2[1].item(id)
		if a>r and b>r and a<w-r and b<h-r:
			#progress(oar.shape,c.shape)
			oar[a-r:a+r,b-r:b+r]=dofunc(oar[a-r:a+r,b-r:b+r],c)
	progress(time.time()-t)
	return oar

def outlineImage(o,radius,i,minz):
	minz=minz-0.0000001#correction test
	t=time.time()
	progress('outline image')
	r=ceil(radius/o.pixsize)
	c=getCircle(r,minz)
	w=len(i)
	h=len(i[0])
	oar=i.copy()
	#oar.fill(-10000000)
	for a in range(r,len(i)-1-r):
		for b in range(r,len(i[0])-1-r):
			p1=i[a,b]
			p2=i[a+1,b]
			p3=i[a,b+1]
			if p1<minz<p2 or p1>minz>p2 or p1<minz<p3 or p1>minz>p3:
				oar[a-r:a+r,b-r:b+r]=numpy.maximum(oar[a-r:a+r,b-r:b+r],c)
	progress(time.time()-t)
	return oar

def dilateAr(ar,cycles):
	for c in range(cycles):
		ar[1:-1,:]=numpy.logical_or(ar[1:-1,:],ar[:-2,:] )
		#ar[1:-1,:]=numpy.logical_or(ar[1:-1,:],ar[2:,:] )
		ar[:,1:-1]=numpy.logical_or(ar[:,1:-1],ar[:,:-2] )
		#ar[:,1:-1]=numpy.logical_or(ar[:,1:-1],ar[:,2:] )
		
def getOffsetImageCavities(o,i):#for pencil operation mainly
	'''detects areas in the offset image which are 'cavities' - the curvature changes.'''
	#i=numpy.logical_xor(lastislice , islice)
	progress('detect corners in the offset image')
	vertical=i[:-2,1:-1]-i[1:-1,1:-1]-o.pencil_threshold> i[1:-1,1:-1]-i[2:,1:-1]
	horizontal=i[1:-1,:-2]-i[1:-1,1:-1]-o.pencil_threshold> i[1:-1,1:-1]-i[1:-1,2:]
	#if bpy.app.debug_value==2:
	
	ar=numpy.logical_or(vertical,horizontal)
	
	
	if 0:#this is newer strategy, finds edges nicely, but pff.going exacty on edge, it has tons of spikes and simply is not better than the old one
		iname=getCachePath(o)+'_pencilthres.exr'
		#numpysave(ar,iname)#save for comparison before
		chunks = imageEdgeSearch_online(o,ar,i)
		iname=getCachePath(o)+'_pencilthres_comp.exr'
		#numpysave(ar,iname)#and after
	else:#here is the old strategy with
		dilateAr(ar,1)
		iname=getCachePath(o)+'_pencilthres.exr'
		#numpysave(ar,iname)#save for comparison before
		
		chunks=imageToChunks(o,ar)
		
		for ch in chunks:#convert 2d chunks to 3d
			for i,p in enumerate(ch.points):
					ch.points[i]=(p[0],p[1],0)
		
		chunks=chunksRefine(chunks,o)
	
	###crop pixels that are on outer borders
	for chi in range(len(chunks)-1,-1,-1):
		chunk=chunks[chi]
		for si in range(len(chunk.points)-1,-1,-1):
			if not(o.min.x<chunk.points[si][0]<o.max.x and o.min.y<chunk.points[si][1]<o.max.y):
				chunk.points.pop(si)
		if len(chunk.points)<2:
			chunks.pop(chi)
			
	return chunks
	
	
def imageEdgeSearch_online(o,ar,zimage):#search edges for pencil strategy, another try.
	t=time.time()
	minx,miny,minz,maxx,maxy,maxz=o.min.x,o.min.y,o.min.z,o.max.x,o.max.y,o.max.z
	pixsize=o.pixsize
	edges=[]
	
	r=3#ceil((o.cutter_diameter/12)/o.pixsize)
	d=2*r
	coef=0.75
	#sx=o.max.x-o.min.x
	#sy=o.max.y-o.min.y
	#size=ar.shape[0]
	maxarx=ar.shape[0]
	maxary=ar.shape[1]
	
	directions=((-1,-1),(0,-1),(1,-1),(1,0),(1,1),(0,1),(-1,1),(-1,0))
	
	indices=ar.nonzero()#first get white pixels
	startpix=ar.sum()#
	totpix=startpix
	chunks=[]
	xs=indices[0][0]
	ys=indices[1][0]
	nchunk=camPathChunk([(xs,ys,zimage[xs,ys])])#startposition
	dindex=0#index in the directions list
	last_direction=directions[dindex]
	test_direction=directions[dindex]
	i=0
	perc=0
	itests=0
	totaltests=0
	maxtests=500
	maxtotaltests=startpix*4
	
	
	ar[xs,ys]=False
	
	while totpix>0 and totaltests<maxtotaltests:#a ratio when the algorithm is allowed to end
		
		if perc!=int(100-100*totpix/startpix):
		   perc=int(100-100*totpix/startpix)
		   progress('pencil path searching',perc)
		#progress('simulation ',int(100*i/l))
		success=False
		testangulardistance=0#distance from initial direction in the list of direction
		testleftright=False#test both sides from last vector
		#achjo=0
		while not success:
			#print(achjo)
			#achjo+=1
			xs=nchunk.points[-1][0]+test_direction[0]
			ys=nchunk.points[-1][1]+test_direction[1]
			
			if xs>r and xs<ar.shape[0]-r and ys>r and ys<ar.shape[1]-r :
				test=ar[xs,ys]
				#print(test)
				if test:
					success=True
			if success:
				nchunk.points.append([xs,ys,zimage[xs,ys]])
				last_direction=test_direction
				ar[xs,ys]=False
				if 0:
					print('success')
					print(xs,ys,testlength,testangle)
					print(lastvect)
					print(testvect)
					print(itests)
			else:
				#nchunk.append([xs,ys])#for debugging purpose
				#ar.shape[0]
				test_direction=last_direction
				if testleftright:
					testangulardistance=-testangulardistance
					testleftright=False
				else:
					testangulardistance=-testangulardistance
					testangulardistance+=1#increment angle
					testleftright=True
				
				if abs(testangulardistance)>6:#/testlength
					testangulardistance=0
					indices=ar.nonzero()
					totpix=len(indices[0])
					chunks.append(nchunk)
					if len(indices[0]>0):
						xs=indices[0][0]
						ys=indices[1][0]
						nchunk=camPathChunk([(xs,ys,zimage[xs,ys])])#startposition
						
						ar[xs,ys]=False
					else:
						nchunk=camPathChunk([])
					
					test_direction=directions[3]
					last_direction=directions[3]
					success=True
					itests=0
					#print('reset')
				if len(nchunk.points)>0:
					if nchunk.points[-1][0]+test_direction[0]<r:
						testvect.x=r
					if nchunk.points[-1][1]+test_direction[1]<r:
						testvect.y=r
					if nchunk.points[-1][0]+test_direction[0]>maxarx-r:
						testvect.x=maxarx-r
					if nchunk.points[-1][1]+test_direction[1]>maxary-r:
						testvect.y=maxary-r

				#dindex=directions.index(last_direction)
				dindexmod=dindex+testangulardistance
				while dindexmod<0:
					dindexmod+=len(directions)
				while dindexmod>len(directions):
					dindexmod-=len(directions)
					
				test_direction=directions[dindexmod]
				if 0:
					print(xs,ys,test_direction,last_direction,testangulardistance)
					print(totpix)
			itests+=1
			totaltests+=1
			
		i+=1
		if i%100==0:
			#print('100 succesfull tests done')
			totpix=ar.sum()
			#print(totpix)
			#print(totaltests)
			i=0
	chunks.append(nchunk)
	for ch in chunks:
		#vecchunk=[]
		#vecchunks.append(vecchunk)
		ch=ch.points
		for i in range(0,len(ch)):
			ch[i]=((ch[i][0]+coef-o.borderwidth)*o.pixsize+minx,(ch[i][1]+coef-o.borderwidth)*o.pixsize+miny,ch[i][2])
			#vecchunk.append(Vector(ch[i]))
	return chunks
	
def crazyPath(o):#TODO: try to do something with this  stuff, it's just a stub. It should be a greedy adaptive algorithm. started another thing below.
	MAX_BEND=0.1#in radians...#TODO: support operation chains ;)
	prepareArea(o)
	#o.millimage = 
	sx=o.max.x-o.min.x
	sy=o.max.y-o.min.y

	resx=ceil(sx/o.simulation_detail)+2*o.borderwidth
	resy=ceil(sy/o.simulation_detail)+2*o.borderwidth

	o.millimage=numpy.array((0.1),dtype=float)
	o.millimage.resize(resx,resy)
	o.millimage.fill(0)
	o.cutterArray=-getCutterArray(o,o.simulation_detail)#getting inverted cutter
	crazy=camPathChunk([(0,0,0)])
	testpos=(o.min.x,o.min.y,o.min.z)

def buildStroke(start,end, cutterArray):
	
	strokelength=max(abs(end[0]-start[0]),abs(end[1]-start[1]))
	size_x = abs(end[0]-start[0])+cutterArray.size[0]
	size_y = abs(end[1]-start[1])+cutterArray.size[0]
	r=cutterArray.size[0]/2
	
	strokeArray=numpy.array((0),dtype=float)
	strokeArray.resize(size_x,size_y)
	strokeArray.fill(-10)
	samplesx=numpy.round(numpy.linspace(start[0],end[0],strokelength))
	samplesy=numpy.round(numpy.linspace(start[1],end[1],strokelength))
	samplesz=numpy.round(numpy.linspace(start[2],end[2],strokelength))
	
	for i in range(0,len(strokelength)):
		#strokeArray(samplesx[i]-r:samplesx[i]+r,samplesy[i]-r:samplesy[i]+r)
		#strokeArray(samplesx[i]-r:samplesx[i]+r,samplesy[i]-r:samplesy[i]+r)
		#cutterArray+samplesz[i]
		strokeArray[samplesx[i]-r:samplesx[i]+r,samplesy[i]-r:samplesy[i]+r] = numpy.maximum(strokeArray[samplesx[i]-r:samplesx[i]+r,samplesy[i]-r:samplesy[i]+r] , cutterArray+samplesz[i])
	return strokeArray

def testStroke():
	pass;
def applyStroke():
	pass;
	
def testStrokeBinary(img, stroke):
	pass;#buildstroke()
	
def crazyStrokeImage(o):#this surprisingly works, and can be used as a basis for something similar to adaptive milling strategy.
	t=time.time()
	minx,miny,minz,maxx,maxy,maxz=o.min.x,o.min.y,o.min.z,o.max.x,o.max.y,o.max.z
	pixsize=o.pixsize
	edges=[]
	
	r=int((o.cutter_diameter/2.0)/o.pixsize)#ceil((o.cutter_diameter/12)/o.pixsize)
	d=2*r
	coef=0.75
	#sx=o.max.x-o.min.x
	#sy=o.max.y-o.min.y
	#size=ar.shape[0]
	
	ar=o.offset_image.copy()
	sampleimage=o.offset_image
	finalstate=o.zbuffer_image
	maxarx=ar.shape[0]
	maxary=ar.shape[1]
	
	cutterArray=getCircleBinary(r)
	cutterArrayNegative=-cutterArray
	#cutterArray=1-cutterArray
	
	cutterimagepix=cutterArray.sum()
	#ar.fill(True)
	satisfypix=cutterimagepix*o.crazy_threshold1#a threshold which says if it is valuable to cut in a direction
	toomuchpix=cutterimagepix*o.crazy_threshold2
	indices=ar.nonzero()#first get white pixels
	startpix=ar.sum()#
	totpix=startpix
	chunks=[]
	xs=indices[0][0]-r
	if xs<r:xs=r
	ys=indices[1][0]-r
	if ys<r:ys=r
	nchunk=camPathChunk([(xs,ys)])#startposition
	print(indices)
	print (indices[0][0],indices[1][0])
	lastvect=Vector((r,0,0))#vector is 3d, blender somehow doesn't rotate 2d vectors with angles.
	testvect=lastvect.normalized()*r/2.0#multiply *2 not to get values <1 pixel
	rot=Euler((0,0,1))
	i=0
	perc=0
	itests=0
	totaltests=0
	maxtests=500
	maxtotaltests=1000000
	
	
	
	print(xs,ys,indices[0][0],indices[1][0],r)
	ar[xs-r:xs-r+d,ys-r:ys-r+d]=ar[xs-r:xs-r+d,ys-r:ys-r+d]*cutterArrayNegative
	anglerange=[-pi,pi]#range for angle of toolpath vector versus material vector
	testangleinit=0
	angleincrement=0.05
	if (o.movement_type=='CLIMB' and o.spindle_rotation_direction=='CCW') or (o.movement_type=='CONVENTIONAL' and o.spindle_rotation_direction=='CW'):
		anglerange=[-pi,0]
		testangleinit=1
		angleincrement=-angleincrement
	elif (o.movement_type=='CONVENTIONAL' and o.spindle_rotation_direction=='CCW') or (o.movement_type=='CLIMB' and o.spindle_rotation_direction=='CW'):
		anglerange=[0,pi]
		testangleinit=-1
		angleincrement=angleincrement
	while totpix>0 and totaltests<maxtotaltests:#a ratio when the algorithm is allowed to end
		
		#if perc!=int(100*totpix/startpix):
		#   perc=int(100*totpix/startpix)
		#   progress('crazy path searching what to mill!',perc)
		#progress('simulation ',int(100*i/l))
		success=False
		# define a vector which gets varied throughout the testing, growing and growing angle to sides.
		testangle=testangleinit
		testleftright=False
		testlength=r
		
		while not success:
			xs=nchunk.points[-1][0]+int(testvect.x)
			ys=nchunk.points[-1][1]+int(testvect.y)
			if xs>r+1 and xs<ar.shape[0]-r-1 and ys>r+1 and ys<ar.shape[1]-r-1 :
				testar=ar[xs-r:xs-r+d,ys-r:ys-r+d]*cutterArray
				if 0:
					print('test')
					print(testar.sum(),satisfypix)
					print(xs,ys,testlength,testangle)
					print(lastvect)
					print(testvect)
					print(totpix)
				
				eatpix=testar.sum()
				cindices=testar.nonzero()
				cx=cindices[0].sum()/eatpix
				cy=cindices[1].sum()/eatpix
				v=Vector((cx-r,cy-r))
				angle=testvect.to_2d().angle_signed(v)
				if anglerange[0]<angle<anglerange[1]:#this could be righthanded milling? lets see :)
					if toomuchpix>eatpix>satisfypix:
						success=True
			if success:
				nchunk.points.append([xs,ys])
				lastvect=testvect
				ar[xs-r:xs-r+d,ys-r:ys-r+d]=ar[xs-r:xs-r+d,ys-r:ys-r+d]*(-cutterArray)
				totpix-=eatpix
				itests=0
				if 0:
					print('success')
					print(xs,ys,testlength,testangle)
					print(lastvect)
					print(testvect)
					print(itests)
			else:
				#nchunk.append([xs,ys])#for debugging purpose
				#ar.shape[0]
				#TODO: after all angles were tested into material higher than toomuchpix, it should cancel, otherwise there is no problem with long travel in free space.....
				#TODO:the testing should start not from the same angle as lastvector, but more towards material. So values closer to toomuchpix are obtained rather than satisfypix
				testvect=lastvect.normalized()*testlength
				right=True
				if testangleinit==0:#meander
					if testleftright:
						testangle=-testangle
						testleftright=False
					else:
						testangle=abs(testangle)+angleincrement#increment angle
						testleftright=True
				else:#climb/conv.
					testangle+=angleincrement
					
				if abs(testangle)>o.crazy_threshold3:#/testlength
					testangle=testangleinit
					testlength+=r/4.0
				if nchunk.points[-1][0]+testvect.x<r:
					testvect.x=r
				if nchunk.points[-1][1]+testvect.y<r:
					testvect.y=r
				if nchunk.points[-1][0]+testvect.x>maxarx-r:
					testvect.x=maxarx-r
				if nchunk.points[-1][1]+testvect.y>maxary-r:
					testvect.y=maxary-r
					
				'''
				if testlength>10:#weird test 
					indices1=ar.nonzero()
					nchunk.append(indices1[0])
					lastvec=Vector((1,0,0))
					testvec=Vector((1,0,0))
					testlength=r
					success=True
				'''
				rot.z=testangle
				
				testvect.rotate(rot)
				if 0:
					print(xs,ys,testlength,testangle)
					print(lastvect)
					print(testvect)
					print(totpix)
			itests+=1
			totaltests+=1
			#achjo
			if itests>maxtests or testlength>r*1.5:
				#print('resetting location')
				indices=ar.nonzero()
				chunks.append(nchunk)
				if len(indices[0])>0:
					index=random.randint(0,len(indices[0])-1)
					#print(index,len(indices[0]))
					xs=indices[0][0]-r
					if xs<r:xs=r
					ys=indices[1][0]-r
					if ys<r:ys=r
					nchunk=camPathChunk([(xs,ys)])#startposition
					ar[xs-r:xs-r+d,ys-r:ys-r+d]=ar[xs-r:xs-r+d,ys-r:ys-r+d]*cutterArrayNegative
					#lastvect=Vector((r,0,0))#vector is 3d, blender somehow doesn't rotate 2d vectors with angles.
					r=random.random()*2*pi
					e=Euler((0,0,r))
					testvect=lastvect.normalized()*4#multiply *2 not to get values <1 pixel
					testvect.rotate(e)
					lastvect=testvect.copy()
				success=True
				itests=0
		#xs=(s.x-o.min.x)/o.simulation_detail+o.borderwidth+o.simulation_detail/2#-m
		#ys=(s.y-o.min.y)/o.simulation_detail+o.borderwidth+o.simulation_detail/2#-m
		i+=1
		if i%100==0:
			print('100 succesfull tests done')
			totpix=ar.sum()
			print(totpix)
			print(totaltests)
			i=0
	chunks.append(nchunk)
	for ch in chunks:
		#vecchunk=[]
		#vecchunks.append(vecchunk)
		ch=ch.points
		for i in range(0,len(ch)):
			ch[i]=((ch[i][0]+coef-o.borderwidth)*o.pixsize+minx,(ch[i][1]+coef-o.borderwidth)*o.pixsize+miny,0)
			#vecchunk.append(Vector(ch[i]))
	return chunks
	
def crazyStrokeImageBinary(o,ar):#this surprisingly works, and can be used as a basis for something similar to adaptive milling strategy.
	t=time.time()
	minx,miny,minz,maxx,maxy,maxz=o.min.x,o.min.y,o.min.z,o.max.x,o.max.y,o.max.z
	pixsize=o.pixsize
	edges=[]
	
	r=int((o.cutter_diameter/2.0)/o.pixsize)#ceil((o.cutter_diameter/12)/o.pixsize)
	d=2*r
	coef=0.75
	#sx=o.max.x-o.min.x
	#sy=o.max.y-o.min.y
	#size=ar.shape[0]
	maxarx=ar.shape[0]
	maxary=ar.shape[1]
	
	cutterArray=getCircleBinary(r)
	cutterArrayNegative=-cutterArray
	#cutterArray=1-cutterArray
	
	cutterimagepix=cutterArray.sum()
	#ar.fill(True)
	satisfypix=cutterimagepix*o.crazy_threshold1#a threshold which says if it is valuable to cut in a direction
	toomuchpix=cutterimagepix*o.crazy_threshold2
	indices=ar.nonzero()#first get white pixels
	startpix=ar.sum()#
	totpix=startpix
	chunks=[]
	xs=indices[0][0]-r
	if xs<r:xs=r
	ys=indices[1][0]-r
	if ys<r:ys=r
	nchunk=camPathChunk([(xs,ys)])#startposition
	print(indices)
	print (indices[0][0],indices[1][0])
	lastvect=Vector((r,0,0))#vector is 3d, blender somehow doesn't rotate 2d vectors with angles.
	testvect=lastvect.normalized()*r/2.0#multiply *2 not to get values <1 pixel
	rot=Euler((0,0,1))
	i=0
	perc=0
	itests=0
	totaltests=0
	maxtests=500
	maxtotaltests=1000000
	
	
	
	print(xs,ys,indices[0][0],indices[1][0],r)
	ar[xs-r:xs-r+d,ys-r:ys-r+d]=ar[xs-r:xs-r+d,ys-r:ys-r+d]*cutterArrayNegative
	anglerange=[-pi,pi]#range for angle of toolpath vector versus material vector
	testangleinit=0
	angleincrement=0.05
	if (o.movement_type=='CLIMB' and o.spindle_rotation_direction=='CCW') or (o.movement_type=='CONVENTIONAL' and o.spindle_rotation_direction=='CW'):
		anglerange=[-pi,0]
		testangleinit=1
		angleincrement=-angleincrement
	elif (o.movement_type=='CONVENTIONAL' and o.spindle_rotation_direction=='CCW') or (o.movement_type=='CLIMB' and o.spindle_rotation_direction=='CW'):
		anglerange=[0,pi]
		testangleinit=-1
		angleincrement=angleincrement
	while totpix>0 and totaltests<maxtotaltests:#a ratio when the algorithm is allowed to end
		
		#if perc!=int(100*totpix/startpix):
		#   perc=int(100*totpix/startpix)
		#   progress('crazy path searching what to mill!',perc)
		#progress('simulation ',int(100*i/l))
		success=False
		# define a vector which gets varied throughout the testing, growing and growing angle to sides.
		testangle=testangleinit
		testleftright=False
		testlength=r
		
		while not success:
			xs=nchunk.points[-1][0]+int(testvect.x)
			ys=nchunk.points[-1][1]+int(testvect.y)
			if xs>r+1 and xs<ar.shape[0]-r-1 and ys>r+1 and ys<ar.shape[1]-r-1 :
				testar=ar[xs-r:xs-r+d,ys-r:ys-r+d]*cutterArray
				if 0:
					print('test')
					print(testar.sum(),satisfypix)
					print(xs,ys,testlength,testangle)
					print(lastvect)
					print(testvect)
					print(totpix)
				
				eatpix=testar.sum()
				cindices=testar.nonzero()
				cx=cindices[0].sum()/eatpix
				cy=cindices[1].sum()/eatpix
				v=Vector((cx-r,cy-r))
				angle=testvect.to_2d().angle_signed(v)
				if anglerange[0]<angle<anglerange[1]:#this could be righthanded milling? lets see :)
					if toomuchpix>eatpix>satisfypix:
						success=True
			if success:
				nchunk.points.append([xs,ys])
				lastvect=testvect
				ar[xs-r:xs-r+d,ys-r:ys-r+d]=ar[xs-r:xs-r+d,ys-r:ys-r+d]*(-cutterArray)
				totpix-=eatpix
				itests=0
				if 0:
					print('success')
					print(xs,ys,testlength,testangle)
					print(lastvect)
					print(testvect)
					print(itests)
			else:
				#nchunk.append([xs,ys])#for debugging purpose
				#ar.shape[0]
				#TODO: after all angles were tested into material higher than toomuchpix, it should cancel, otherwise there is no problem with long travel in free space.....
				#TODO:the testing should start not from the same angle as lastvector, but more towards material. So values closer to toomuchpix are obtained rather than satisfypix
				testvect=lastvect.normalized()*testlength
				right=True
				if testangleinit==0:#meander
					if testleftright:
						testangle=-testangle
						testleftright=False
					else:
						testangle=abs(testangle)+angleincrement#increment angle
						testleftright=True
				else:#climb/conv.
					testangle+=angleincrement
					
				if abs(testangle)>o.crazy_threshold3:#/testlength
					testangle=testangleinit
					testlength+=r/4.0
				if nchunk.points[-1][0]+testvect.x<r:
					testvect.x=r
				if nchunk.points[-1][1]+testvect.y<r:
					testvect.y=r
				if nchunk.points[-1][0]+testvect.x>maxarx-r:
					testvect.x=maxarx-r
				if nchunk.points[-1][1]+testvect.y>maxary-r:
					testvect.y=maxary-r
					
				'''
				if testlength>10:#weird test 
					indices1=ar.nonzero()
					nchunk.append(indices1[0])
					lastvec=Vector((1,0,0))
					testvec=Vector((1,0,0))
					testlength=r
					success=True
				'''
				rot.z=testangle
				
				testvect.rotate(rot)
				if 0:
					print(xs,ys,testlength,testangle)
					print(lastvect)
					print(testvect)
					print(totpix)
			itests+=1
			totaltests+=1
			#achjo
			if itests>maxtests or testlength>r*1.5:
				#print('resetting location')
				indices=ar.nonzero()
				chunks.append(nchunk)
				if len(indices[0])>0:
					index=random.randint(0,len(indices[0])-1)
					#print(index,len(indices[0]))
					xs=indices[0][0]-r
					if xs<r:xs=r
					ys=indices[1][0]-r
					if ys<r:ys=r
					nchunk=camPathChunk([(xs,ys)])#startposition
					ar[xs-r:xs-r+d,ys-r:ys-r+d]=ar[xs-r:xs-r+d,ys-r:ys-r+d]*cutterArrayNegative
					#lastvect=Vector((r,0,0))#vector is 3d, blender somehow doesn't rotate 2d vectors with angles.
					r=random.random()*2*pi
					e=Euler((0,0,r))
					testvect=lastvect.normalized()*4#multiply *2 not to get values <1 pixel
					testvect.rotate(e)
					lastvect=testvect.copy()
				success=True
				itests=0
		#xs=(s.x-o.min.x)/o.simulation_detail+o.borderwidth+o.simulation_detail/2#-m
		#ys=(s.y-o.min.y)/o.simulation_detail+o.borderwidth+o.simulation_detail/2#-m
		i+=1
		if i%100==0:
			print('100 succesfull tests done')
			totpix=ar.sum()
			print(totpix)
			print(totaltests)
			i=0
	chunks.append(nchunk)
	for ch in chunks:
		#vecchunk=[]
		#vecchunks.append(vecchunk)
		ch=ch.points
		for i in range(0,len(ch)):
			ch[i]=((ch[i][0]+coef-o.borderwidth)*o.pixsize+minx,(ch[i][1]+coef-o.borderwidth)*o.pixsize+miny,0)
			#vecchunk.append(Vector(ch[i]))
	return chunks
	
def imageToChunks(o,image):
	t=time.time()
	minx,miny,minz,maxx,maxy,maxz=o.min.x,o.min.y,o.min.z,o.max.x,o.max.y,o.max.z
	pixsize=o.pixsize
	
	#progress('detecting outline')
	edges=[]
	ar = image[:,:-1]-image[:,1:] 
	
	indices1=ar.nonzero()
	borderspread=2#o.cutter_diameter/o.pixsize#when the border was excluded precisely, sometimes it did remove some silhouette parts
	r=o.borderwidth-borderspread# to prevent outline of the border was 3 before and also (o.cutter_diameter/2)/pixsize+o.borderwidth
	w=image.shape[0]
	h=image.shape[1]
	coef=0.75#compensates for imprecisions
	for id in range(0,len(indices1[0])):
		a=indices1[0][id]
		b=indices1[1][id]
		if r<a<w-r and r<b<h-r:
			edges.append(((a-1,b),(a,b)))
					
	ar=image[:-1,:]-image[1:,:]
	indices2=ar.nonzero()
	for id in range(0,len(indices2[0])):
		a=indices2[0][id]
		b=indices2[1][id]
		if r<a<w-r and r<b<h-r:
			edges.append(((a,b-1),(a,b)))
	
	i=0 
	chi=0
	
	polychunks=[]
	#progress(len(edges))
	
	d={}
	for e in edges:
		d[e[0]]=[]
		d[e[1]]=[]
	for e in edges:
		
		verts1=d[e[0]]
		verts2=d[e[1]]
		verts1.append(e[1])
		verts2.append(e[0])
		
	#progress(time.time()-t)
	t=time.time()
	if len(edges)>0:
	
		ch=[edges[0][0],edges[0][1]]#first and his reference
		
		d[edges[0][0]].remove(edges[0][1])
		#d.pop(edges[0][0])
	
		i=0
		#verts=[123]
		specialcase=0
		closed=False
		#progress('condensing outline')
		while len(d)>0 and i<20000000:# and verts!=[]:  ####bacha na pripade krizku takzvane, kdy dva pixely na sebe uhlopricne jsou
			verts=d.get(ch[-1],[])
			closed=False
			#print(verts)
			
			if len(verts)<=1:# this will be good for not closed loops...some time
				closed=True
				if len(verts)==1:
					ch.append(verts[0])
					verts.remove(verts[0])
			elif len(verts)>=3:
					specialcase+=1
					#if specialcase>=2:
						#print('thisisit')
					v1=ch[-1]
					v2=ch[-2]
					white=image[v1[0],v1[1]]
					comesfromtop=v1[1]<v2[1]
					comesfrombottom=v1[1]>v2[1]
					comesfromleft=v1[0]>v2[0]
					comesfromright=v1[0]<v2[0]
					take=False
					for v in verts:
						if (v[0]==ch[-2][0] and v[1]==ch[-2][1]):
							pass;
							verts.remove(v)
						
						if not take:
							if (not white and comesfromtop)or ( white and comesfrombottom):#goes right
								if v1[0]+0.5<v[0]:
									take=True
							elif (not white and comesfrombottom)or ( white and comesfromtop):#goes left
								if v1[0]>v[0]+0.5:
									take=True
							elif (not white and comesfromleft)or ( white and comesfromright):#goes down
								if v1[1]>v[1]+0.5:
									take=True
							elif (not white and comesfromright)or ( white and comesfromleft):#goes up
								if v1[1]+0.5<v[1]:
									take=True
							if take:
								ch.append(v)
								verts.remove(v)
							#   break
							
			else:#here it has to be 2 always
				done=False
				for vi in range(len(verts)-1,-1,-1):
					if not done:
						v=verts[vi]
						if (v[0]==ch[-2][0] and v[1]==ch[-2][1]):
							pass
							verts.remove(v)
						else:
						
							ch.append(v)
							done=True
							verts.remove(v)
							if (v[0]==ch[0][0] and v[1]==ch[0][1]):# or len(verts)<=1:
								closed=True
								
			if closed:
				polychunks.append(ch)
				for si,s in enumerate(ch):
					#print(si)
					if si>0:#first one was popped 
						if d.get(s,None)!=None and len(d[s])==0:#this makes the case much less probable, but i think not impossible
							d.pop(s)
				if len(d)>0:
					newch=False
					while not newch:
						v1=d.popitem()
						if len(v1[1])>0:
							ch=[v1[0],v1[1][0]]
							newch=True
				
					
					#print(' la problema grandiosa')
			i+=1
			if i%10000==0:
				print(len(ch))
				#print(polychunks)
				print(i)
			
		#polychunks.append(ch)
		
		vecchunks=[]
		#p=Polygon.Polygon()
		
		for ch in polychunks:
			vecchunk=[]
			vecchunks.append(vecchunk)
			for i in range(0,len(ch)):
				ch[i]=((ch[i][0]+coef-o.borderwidth)*pixsize+minx,(ch[i][1]+coef-o.borderwidth)*pixsize+miny,0)
				vecchunk.append(Vector(ch[i]))
		t=time.time()
		#print('optimizing outline')
		
		#print('directsimplify')
		#p=Polygon.Polygon()
		reduxratio=1.25#was 1.25
		soptions=['distance','distance',o.pixsize*reduxratio,5,o.pixsize*reduxratio]
		#soptions=['distance','distance',0.0,5,0,5,0]#o.pixsize*1.25,5,o.pixsize*1.25]
		#polychunks=[]
		nchunks=[]
		for i,ch in enumerate(vecchunks):
			
			s=curve_simplify.simplify_RDP(ch, soptions)
			#print(s)
			nch=camPathChunk([])
			for i in range(0,len(s)):
				nch.points.append((ch[s[i]].x,ch[s[i]].y))
				
			if len(nch.points)>2:
				#polychunks[i].points=nch
				nchunks.append(nch)
		#m=  
		
		return nchunks
	else:
		return []
	
def imageToPoly(o,i):
	polychunks=imageToChunks(o,i)
	polys=chunksToPolys(polychunks)
	
	#polys=orderPoly(polys)
	t=time.time()
	
	return polys#[polys]


def getSampleImage(s,sarray,minz):
	
	x=s[0]
	y=s[1]
	if (x<0 or x>len(sarray)-1) or (y<0 or y>len(sarray[0])-1):
		return -10
		#return None;#(sarray[y,x] bugs
	else:
		#return(sarray[int(x),int(y)])
		minx=floor(x)
		maxx=ceil(x)
		if maxx==minx:
			maxx+=1
		miny=floor(y)
		maxy=ceil(y)
		if maxy==miny:
			maxy+=1
		
		'''
		s1a=sarray[minx,miny]#
		s2a=sarray[maxx,miny]
		s1b=sarray[minx,maxy]
		s2b=sarray[maxx,maxy]
		'''
		s1a=sarray.item(minx,miny)#
		s2a=sarray.item(maxx,miny)
		s1b=sarray.item(minx,maxy)
		s2b=sarray.item(maxx,maxy)
		
		#if s1a==minz and s2a==minz and s1b==minz and s2b==minz:
		#  return
		'''
		if min(s1a,s2a,s1b,s2b)<-10:
			#return -10
			if s1a<-10:
				s1a=s2a
			if s2a<-10:
				s2a=s1a
			if s1b<-10:
				s1b=s2b
			if s2b<-10:
				s2b=s1b
	
			sa=s1a*(maxx-x)+s2a*(x-minx)
			sb=s1b*(maxx-x)+s2b*(x-minx)
			if sa<-10:
				sa=sb
			if sb<-10:
				sb=sa
			z=sa*(maxy-y)+sb*(y-miny)
			return z
			
		else:
		''' 
		sa=s1a*(maxx-x)+s2a*(x-minx)
		sb=s1b*(maxx-x)+s2b*(x-minx)
		z=sa*(maxy-y)+sb*(y-miny)
		return z
		
def getResolution(o):
	sx=o.max.x-o.min.x
	sy=o.max.y-o.min.y

	resx=ceil(sx/o.pixsize)+2*o.borderwidth
	resy=ceil(sy/o.pixsize)+2*o.borderwidth
#this basically renders blender zbuffer and makes it accessible by saving & loading it again.
#that's because blender doesn't allow accessing pixels in render :(
def renderSampleImage(o):
	t=time.time()
	progress('getting zbuffer')
	
	
	if o.geometry_source=='OBJECT' or o.geometry_source=='GROUP':
		pixsize=o.pixsize

		sx=o.max.x-o.min.x
		sy=o.max.y-o.min.y
	
		resx=ceil(sx/o.pixsize)+2*o.borderwidth
		resy=ceil(sy/o.pixsize)+2*o.borderwidth
		
		####setup image name
		#fn=bpy.data.filepath
		#iname=bpy.path.abspath(fn)
		#l=len(bpy.path.basename(fn))
		iname=getCachePath(o)+'_z.exr'
		if not o.update_zbufferimage_tag:
			try:
				i=bpy.data.images.load(iname)
			except:
				o.update_zbufferimage_tag=True
		if o.update_zbufferimage_tag:
			s=bpy.context.scene
		
			#prepare nodes first
			s.use_nodes=True
			n=s.node_tree
			
			n.links.clear()
			n.nodes.clear()
			n1=n.nodes.new('CompositorNodeRLayers')
			n2=n.nodes.new('CompositorNodeViewer')
			n3=n.nodes.new('CompositorNodeComposite')
			n.links.new(n1.outputs['Z'],n2.inputs['Image'])
			n.links.new(n1.outputs['Z'],n3.inputs['Image']) 
			n.nodes.active=n2
			###################
				
			r=s.render
			r.resolution_x=resx
			r.resolution_y=resy
			
			#resize operation image
			o.offset_image.resize((resx,resy))
			o.offset_image.fill(-10)
			
			#various settings for  faster render
			r.tile_x=1024#ceil(resx/1024)
			r.tile_y=1024#ceil(resy/1024)
			r.resolution_percentage=100
			
			r.engine='BLENDER_RENDER'
			r.use_antialiasing=False
			r.use_raytrace=False
			r.use_shadows=False
			ff=r.image_settings.file_format
			cm=r.image_settings.color_mode
			r.image_settings.file_format='OPEN_EXR'
			r.image_settings.color_mode='BW'
			r.image_settings.color_depth='32'
			
			#camera settings
			camera=s.camera
			if camera==None:
				bpy.ops.object.camera_add(view_align=False, enter_editmode=False, location=(0,0,0), rotation=(0,0,0))
				camera=bpy.context.active_object
				bpy.context.scene.camera=camera
				#bpy.ops.view3d.object_as_camera()

			camera.data.type='ORTHO'
			camera.data.ortho_scale=max(resx*o.pixsize,resy*o.pixsize)
			camera.location=(o.min.x+sx/2,o.min.y+sy/2,1)
			camera.rotation_euler=(0,0,0)
			#if not o.render_all:#removed in 0.3
			
			h=[]
			
			#ob=bpy.data.objects[o.object_name]
			for ob in s.objects:
				h.append(ob.hide_render)
				ob.hide_render=True
			for ob in o.objects:
				ob.hide_render=False
			 
			bpy.ops.render.render()
			
			#if not o.render_all:
			for id,obs in enumerate(s.objects):
				obs.hide_render=h[id]
			
				
			imgs=bpy.data.images
			for isearch in imgs:
				if len(isearch.name)>=13:
					if isearch.name[:13]=='Render Result':
						i=isearch
						
						
						#progress(iname)
						i.save_render(iname)
						
			
			r.image_settings.file_format=ff   
			r.image_settings.color_mode=cm
		
			i=bpy.data.images.load(iname)
			bpy.context.scene.render.engine='BLENDERCAM_RENDER'
		a=imagetonumpy(i)
		a=1.0-a
		o.zbuffer_image=a
		o.update_zbufferimage_tag=False
		
	else:
		i=bpy.data.images[o.source_image_name]
		sx=int(i.size[0]*o.source_image_crop_start_x/100.0)
		ex=int(i.size[0]*o.source_image_crop_end_x/100.0)
		sy=int(i.size[1]*o.source_image_crop_start_y/100.0)
		ey=int(i.size[1]*o.source_image_crop_end_y/100.0)
		o.offset_image.resize(ex-sx+2*o.borderwidth,ey-sy+2*o.borderwidth)
		
		
		
		o.pixsize=o.source_image_size_x/i.size[0]
		progress('pixel size in the image source', o.pixsize)
		
		rawimage=imagetonumpy(i)
		maxa=numpy.max(rawimage)
		mina=numpy.min(rawimage)
		a=numpy.array((1.0,1.0))
		a.resize(2*o.borderwidth+i.size[0],2*o.borderwidth+i.size[1])
		if o.strategy=='CUTOUT':#cutout strategy doesn't want to cut image border
			a.fill(0)
		else:#other operations want to avoid cutting anything outside image borders.
			a.fill(o.min.z)
		#2*o.borderwidth
		a[o.borderwidth:-o.borderwidth,o.borderwidth:-o.borderwidth]=rawimage
		a=a[sx:ex+o.borderwidth*2,sy:ey+o.borderwidth*2]
		
		a=(a-mina)#TODO: fix this!!!!!
		a*=o.source_image_scale_z
		a+=o.source_image_offset.z
		o.minz=numpy.min(a)
		o.min.z=numpy.min(a)
		print('min z ', o.min.z)
		print('max z ', o.max.z)
		print('max image ', numpy.max(a))
		print('min image ', numpy.min(a))
		o.zbuffer_image=a
	#progress('got z buffer also with conversion in:')
	progress(time.time()-t)
	
	#progress(a)
	o.update_zbufferimage_tag=False
	return o.zbuffer_image
	#return numpy.array([])

def prepareArea(o):
	#if not o.use_exact:
	renderSampleImage(o)
	samples=o.zbuffer_image
	
	iname=getCachePath(o)+'_off.exr'

	if not o.update_offsetimage_tag:
		progress('loading offset image')
		try:
			o.offset_image=imagetonumpy(bpy.data.images.load(iname))
		except:
			o.update_offsetimage_tag=True;
		
	if o.update_offsetimage_tag:
		if o.inverse:
			samples=numpy.maximum(samples,o.min.z-0.00001)
		offsetArea(o,samples)
		numpysave(o.offset_image,iname)
		