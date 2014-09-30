import bpy
from bpy.types import UIList

def getUnit():
	if bpy.context.scene.unit_settings.system == 'METRIC':
		return 'mm'
	elif bpy.context.scene.unit_settings.system == 'IMPERIAL':
		return "''"
		
####Panel definitions
class CAMButtonsPanel():
	bl_space_type = 'PROPERTIES'
	bl_region_type = 'WINDOW'
	bl_context = "render"
	# COMPAT_ENGINES must be defined in each subclass, external engines can add themselves here
	
	@classmethod
	def poll(cls, context):
		rd = context.scene.render
		return rd.engine in cls.COMPAT_ENGINES
	

class CAM_CUTTER_Panel(CAMButtonsPanel, bpy.types.Panel):   
	"""CAM cutter panel"""
	bl_label = " "
	bl_idname = "WORLD_PT_CAM_CUTTER"
		
	COMPAT_ENGINES = {'BLENDERCAM_RENDER'}
	
	def draw_header(self, context):
	   self.layout.menu("CAM_CUTTER_presets", text="CAM Cutter")
		
	def draw(self, context):
		layout = self.layout
		d=bpy.context.scene
		if len(d.cam_operations)>0:
			ao=d.cam_operations[d.cam_active_operation]
		
			if ao:
				#cutter preset
				row = layout.row(align=True)
				row.menu("CAM_CUTTER_presets", text=bpy.types.CAM_CUTTER_presets.bl_label)
				row.operator("render.cam_preset_cutter_add", text="", icon='ZOOMIN')
				row.operator("render.cam_preset_cutter_add", text="", icon='ZOOMOUT').remove_active = True
				layout.prop(ao,'cutter_id')
				layout.prop(ao,'cutter_type')
				layout.prop(ao,'cutter_diameter')
				#layout.prop(ao,'cutter_length')
				layout.prop(ao,'cutter_flutes')
				if ao.cutter_type=='VCARVE':
					layout.prop(ao,'cutter_tip_angle')
				if ao.cutter_type=='CUSTOM':
					layout.prop_search(ao, "cutter_object_name", bpy.data, "objects")

   
class CAM_MACHINE_Panel(CAMButtonsPanel, bpy.types.Panel):	
	"""CAM machine panel"""
	bl_label = " "
	bl_idname = "WORLD_PT_CAM_MACHINE"
		
	COMPAT_ENGINES = {'BLENDERCAM_RENDER'}
	
	def draw_header(self, context):
	   self.layout.menu("CAM_MACHINE_presets", text="CAM Machine")
		
	def draw(self, context):
		layout = self.layout
		s=bpy.context.scene
		us=s.unit_settings
		
		ao=s.cam_machine
	
		if ao:
			#cutter preset
			row = layout.row(align=True)
			row.menu("CAM_MACHINE_presets", text=bpy.types.CAM_MACHINE_presets.bl_label)
			row.operator("render.cam_preset_machine_add", text="", icon='ZOOMIN')
			row.operator("render.cam_preset_machine_add", text="", icon='ZOOMOUT').remove_active = True
			#layout.prop(ao,'name')
			layout.prop(ao,'post_processor')
			layout.prop(ao,'eval_splitting')
			if ao.eval_splitting:
				layout.prop(ao,'split_limit')
			
			layout.prop(us,'system')
			layout.prop(ao,'working_area')
			layout.prop(ao,'feedrate_min')
			layout.prop(ao,'feedrate_max')
			#layout.prop(ao,'feedrate_default')
			layout.prop(ao,'spindle_min')
			layout.prop(ao,'spindle_max')
			#layout.prop(ao,'spindle_default')
			#layout.prop(ao,'axis4')
			#layout.prop(ao,'axis5')
			#layout.prop(ao,'collet_size')
			#

class CAM_MATERIAL_Panel(CAMButtonsPanel, bpy.types.Panel):	 
	"""CAM material panel"""
	bl_label = "CAM Material size and position"
	bl_idname = "WORLD_PT_CAM_MATERIAL"
		
	COMPAT_ENGINES = {'BLENDERCAM_RENDER'}
	
	def draw(self, context):
		layout = self.layout
		scene=bpy.context.scene
		
		if len(scene.cam_operations)==0:
			layout.label('Add operation first')
		if len(scene.cam_operations)>0:
			ao=scene.cam_operations[scene.cam_active_operation]
			if ao:
				#print(dir(layout))
				layout.template_running_jobs()
				if ao.geometry_source=='OBJECT' or ao.geometry_source=='GROUP':
					row = layout.row(align=True)
					layout.prop(ao,'material_from_model')
					
					if ao.material_from_model:
						layout.prop(ao,'material_radius_around_model')
					else:
						layout.prop(ao,'material_origin')
						layout.prop(ao,'material_size')
						
					layout.operator("object.cam_position", text="Position object")
				else:
					layout.label('Estimated from image')
		
class CAM_UL_operations(UIList):
	def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
		# assert(isinstance(item, bpy.types.VertexGroup)
		operation = item
		if self.layout_type in {'DEFAULT', 'COMPACT'}:
			
			layout.label(text=item.name, translate=False, icon_value=icon)
			icon = 'LOCKED' if operation.computing else 'UNLOCKED'
			if operation.computing:
				layout.label(text=operation.outtext)#"computing" )
		elif self.layout_type in {'GRID'}:
			 layout.alignment = 'CENTER'
			 layout.label(text="", icon_value=icon)
			 
class CAM_UL_chains(UIList):
	def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
		# assert(isinstance(item, bpy.types.VertexGroup)
		chain = item
		if self.layout_type in {'DEFAULT', 'COMPACT'}:
			
			layout.label(text=item.name, translate=False, icon_value=icon)
			icon = 'LOCKED' if chain.computing else 'UNLOCKED'
			if chain.computing:
				layout.label(text="computing" )
		elif self.layout_type in {'GRID'}:
			 layout.alignment = 'CENTER'
			 layout.label(text="", icon_value=icon)
			 
class CAM_CHAINS_Panel(CAMButtonsPanel, bpy.types.Panel):
	"""CAM chains panel"""
	bl_label = "CAM chains"
	bl_idname = "WORLD_PT_CAM_CHAINS"
		
	COMPAT_ENGINES = {'BLENDERCAM_RENDER'}
	
	

	def draw(self, context):
		layout = self.layout
		
		row = layout.row() 
		scene=bpy.context.scene
		
		row.template_list("CAM_UL_chains", '', scene, "cam_chains", scene, 'cam_active_chain')
		col = row.column(align=True)
		col.operator("scene.cam_chain_add", icon='ZOOMIN', text="")
		#col.operator("scene.cam_operation_copy", icon='COPYDOWN', text="")
		col.operator("scene.cam_chain_remove",icon='ZOOMOUT', text="")
		#if group:
		#col.separator()
		#col.operator("scene.cam_operation_move", icon='TRIA_UP', text="").direction = 'UP'
		#col.operator("scene.cam_operation_move", icon='TRIA_DOWN', text="").direction = 'DOWN'
		#row = layout.row() 
	   
		if len(scene.cam_chains)>0:
			chain=scene.cam_chains[scene.cam_active_chain]

			row = layout.row(align=True)
			
			if chain:
				row.template_list("CAM_UL_operations", '', chain, "operations", chain, 'active_operation')
				col = row.column(align=True)
				col.operator("scene.cam_chain_operation_add", icon='ZOOMIN', text="")
				col.operator("scene.cam_chain_operation_remove",icon='ZOOMOUT', text="")

				if not chain.computing:
					if chain.valid:
						pass
						layout.operator("object.calculate_cam_paths_chain", text="Export chain gcode")
						#layout.operator("object.calculate_cam_paths_background", text="Calculate path in background")
						layout.operator("object.cam_simulate_chain", text="Simulate this chain")
					else:
						layout.label("chain invalid, can't compute")
				else:
					layout.label('chain is currently computing')
					#layout.prop(ao,'computing')
				
				layout.prop(chain,'name')
				layout.prop(chain,'filename')
		
			 
class CAM_OPERATIONS_Panel(CAMButtonsPanel, bpy.types.Panel):
	"""CAM operations panel"""
	bl_label = "CAM operations"
	bl_idname = "WORLD_PT_CAM_OPERATIONS"
	
	
	COMPAT_ENGINES = {'BLENDERCAM_RENDER'}
	
	

	def draw(self, context):
		layout = self.layout
		
		row = layout.row() 
		scene=bpy.context.scene
		row.template_list("CAM_UL_operations", '', scene, "cam_operations", scene, 'cam_active_operation')
		col = row.column(align=True)
		col.operator("scene.cam_operation_add", icon='ZOOMIN', text="")
		col.operator("scene.cam_operation_copy", icon='COPYDOWN', text="")
		col.operator("scene.cam_operation_remove",icon='ZOOMOUT', text="")
		#if group:
		col.separator()
		col.operator("scene.cam_operation_move", icon='TRIA_UP', text="").direction = 'UP'
		col.operator("scene.cam_operation_move", icon='TRIA_DOWN', text="").direction = 'DOWN'
		#row = layout.row() 
	   
		if len(scene.cam_operations)>0:
			ao=scene.cam_operations[scene.cam_active_operation]

			row = layout.row(align=True)
			row.menu("CAM_OPERATION_presets", text=bpy.types.CAM_OPERATION_presets.bl_label)
			row.operator("render.cam_preset_operation_add", text="", icon='ZOOMIN')
			row.operator("render.cam_preset_operation_add", text="", icon='ZOOMOUT').remove_active = True
			
			if ao:
				if not ao.computing:
					if ao.valid:
						layout.operator("object.calculate_cam_path", text="Calculate path")
						layout.operator("object.calculate_cam_paths_background", text="Calculate path in background")
						if ao.path_object_name!=None and scene.objects.get(ao.path_object_name)!=None:
							layout.operator("object.cam_export", text="Export gcode")		
						layout.operator("object.cam_simulate", text="Simulate this operation")

							
					else:
						layout.label("operation invalid, can't compute")
				else:
					layout.label('operation is currently computing')
					#layout.prop(ao,'computing')
				
				layout.prop(ao,'name')
				layout.prop(ao,'filename')
				layout.prop(ao,'auto_export')
				layout.prop(ao,'geometry_source')
				if not ao.strategy=='CURVE':
					if ao.geometry_source=='OBJECT':
						layout.prop_search(ao, "object_name", bpy.data, "objects")
					elif ao.geometry_source=='GROUP':
						layout.prop_search(ao, "group_name", bpy.data, "groups")
					else:
						layout.prop_search(ao, "source_image_name", bpy.data, "images")
				
 
				if ao.strategy=='CARVE' or ao.strategy=='CURVE':
					layout.prop_search(ao, "curve_object", bpy.data, "objects")
				

									 
class CAM_INFO_Panel(CAMButtonsPanel, bpy.types.Panel):
	"""CAM info panel"""
	bl_label = "CAM info & warnings"
	bl_idname = "WORLD_PT_CAM_INFO"	  
	
	COMPAT_ENGINES = {'BLENDERCAM_RENDER'}
	
	def draw(self, context):
		layout = self.layout
		scene=bpy.context.scene
		row = layout.row() 
		if len(scene.cam_operations)==0:
			layout.label('Add operation first')
		if len(scene.cam_operations)>0:
			ao=scene.cam_operations[scene.cam_active_operation]
			if ao.warnings!='':
				lines=ao.warnings.split('\n')
				for l in lines:
					layout.label(l)
			if ao.valid:
				#ob=bpy.data.objects[ao.object_name]
				#layout.separator()
				if ao.duration>0:
					layout.label('operation time: '+str(int(ao.duration*100)/100.0)+' min')	   
				#layout.prop(ao,'chipload')
				layout.label(  'chipload: '+str(round(ao.chipload,6))+getUnit()+' / tooth')
				#layout.label(str(ob.dimensions.x))
				#row=layout.row()
		
class CAM_OPERATION_PROPERTIES_Panel(CAMButtonsPanel, bpy.types.Panel):
	"""CAM operation properties panel"""
	bl_label = "CAM operation setup"
	bl_idname = "WORLD_PT_CAM_OPERATION"
	
	
	COMPAT_ENGINES = {'BLENDERCAM_RENDER'}
	
	

	def draw(self, context):
		layout = self.layout
		scene=bpy.context.scene
		
			
		row = layout.row() 
		if len(scene.cam_operations)==0:
			layout.label('Add operation first')
		if len(scene.cam_operations)>0:
			ao=scene.cam_operations[scene.cam_active_operation]
			if ao.valid:
				layout.prop(ao,'machine_axes')
				if ao.machine_axes=='3':
					layout.prop(ao,'strategy')
				elif ao.machine_axes=='4':
					layout.prop(ao,'strategy4axis')
				elif ao.machine_axes=='5':
					layout.prop(ao,'strategy5axis')
				if ao.strategy=='BLOCK' or ao.strategy=='SPIRAL' or ao.strategy=='CIRCLES':
					layout.prop(ao,'movement_insideout')
					
				#if ao.geometry_source=='OBJECT' or ao.geometry_source=='GROUP':
					'''
					o=bpy.data.objects[ao.object_name]
					
					if o.type=='MESH' and (ao.strategy=='DRILL'):
						layout.label('Not supported for meshes')
						return
					'''
					#elif o.type=='CURVE' and (ao.strategy!='CARVE' and ao.strategy!='POCKET' and ao.strategy!='DRILL' and ao.strategy!='CUTOUT'):
					 #	 layout.label('Not supported for curves')
					 #	 return
					
				if ao.strategy=='CUTOUT':
					layout.prop(ao,'cut_type')
					#layout.prop(ao,'dist_between_paths')
					layout.prop(ao,'outlines_count')
					if ao.outlines_count>1:
						layout.prop(ao,'dist_between_paths')
						layout.prop(ao,'movement_insideout')
					layout.prop(ao,'dont_merge')
					layout.prop(ao,'use_bridges')
					if ao.use_bridges:
						layout.prop(ao,'bridges_width')
						layout.prop(ao,'bridges_height')
						layout.prop(ao,'bridges_per_curve')
						layout.prop(ao,'bridges_max_distance')
					
				elif ao.strategy=='WATERLINE':
					layout.prop(ao,'slice_detail')	
					layout.prop(ao,'waterline_fill')  
					if ao.waterline_fill:
						layout.prop(ao,'dist_between_paths')			
						layout.prop(ao,'waterline_project')
					layout.prop(ao,'skin')
					layout.prop(ao,'inverse')
				elif ao.strategy=='CARVE':
					layout.prop(ao,'carve_depth')
					layout.prop(ao,'dist_along_paths')
				elif ao.strategy=='PENCIL':
					layout.prop(ao,'dist_along_paths')
					layout.prop(ao,'pencil_threshold')
				elif ao.strategy=='CRAZY':
					layout.prop(ao,'crazy_threshold1')
					layout.prop(ao,'crazy_threshold2')
					layout.prop(ao,'crazy_threshold3')
					layout.prop(ao,'crazy_threshold4')
					layout.prop(ao,'dist_between_paths')
					layout.prop(ao,'dist_along_paths')
				elif ao.strategy=='DRILL':
					layout.prop(ao,'drill_type')
				else:				 
					layout.prop(ao,'dist_between_paths')
					layout.prop(ao,'dist_along_paths')
					if ao.strategy=='PARALLEL' or ao.strategy=='CROSS':
						layout.prop(ao,'parallel_angle')
						if not ao.use_layers:
							layout.prop(ao,'parallel_step_back')
						
					layout.prop(ao,'skin')
					layout.prop(ao,'inverse')
				#elif ao.strategy=='SLICES':
				#	layout.prop(ao,'slice_detail')	
			#first attempt to draw object list for orientations:
				
				
class CAM_MOVEMENT_Panel(CAMButtonsPanel, bpy.types.Panel):
	"""CAM movement panel"""
	bl_label = "CAM movement"
	bl_idname = "WORLD_PT_CAM_MOVEMENT"	  
	
	COMPAT_ENGINES = {'BLENDERCAM_RENDER'}
	
	def draw(self, context):
		layout = self.layout
		scene=bpy.context.scene
		row = layout.row() 
		if len(scene.cam_operations)==0:
			layout.label('Add operation first')
		if len(scene.cam_operations)>0:
			ao=scene.cam_operations[scene.cam_active_operation]
			if ao.valid:
				layout.prop(ao,'movement_type')
				if ao.movement_type=='BLOCK' or ao.movement_type=='SPIRAL' or ao.movement_type=='CIRCLES':
					layout.prop(ao,'movement_insideout')
				   
				layout.prop(ao,'spindle_rotation_direction')
				layout.prop(ao,'free_movement_height')
				if ao.strategy=='CUTOUT':
					layout.prop(ao,'first_down')
					#if ao.first_down:
					
				if ao.strategy=='POCKET':
					layout.prop(ao,'helix_enter')
					if ao.helix_enter:
						layout.prop(ao,'ramp_in_angle')
						layout.prop(ao,'helix_diameter')
					layout.prop(ao,'retract_tangential')
					if ao.retract_tangential:
						layout.prop(ao,'retract_radius')
						layout.prop(ao,'retract_height')
				
				layout.prop(ao,'ramp')
				if ao.ramp:
					layout.prop(ao,'ramp_in_angle')
					layout.prop(ao,'ramp_out')
					if ao.ramp_out:
						
						layout.prop(ao,'ramp_out_angle')
					
				layout.prop(ao,'stay_low')
				layout.prop(ao,'protect_vertical')
				if ao.protect_vertical:
					layout.prop(ao,'protect_vertical_limit')
			  
				
class CAM_FEEDRATE_Panel(CAMButtonsPanel, bpy.types.Panel):
	"""CAM feedrate panel"""
	bl_label = "CAM feedrate"
	bl_idname = "WORLD_PT_CAM_FEEDRATE"	  
	
	COMPAT_ENGINES = {'BLENDERCAM_RENDER'}
	
	def draw(self, context):
		layout = self.layout
		scene=bpy.context.scene
		row = layout.row() 
		if len(scene.cam_operations)==0:
			layout.label('Add operation first')
		if len(scene.cam_operations)>0:
			ao=scene.cam_operations[scene.cam_active_operation]
			if ao.valid:
				layout.prop(ao,'feedrate')
				layout.prop(ao,'plunge_feedrate')
				layout.prop(ao,'plunge_angle')
				layout.prop(ao,'spindle_rpm')

class CAM_OPTIMISATION_Panel(CAMButtonsPanel, bpy.types.Panel):
	"""CAM optimisation panel"""
	bl_label = "CAM optimisation"
	bl_idname = "WORLD_PT_CAM_OPTIMISATION"
	
	COMPAT_ENGINES = {'BLENDERCAM_RENDER'}
	
	

	def draw(self, context):
		layout = self.layout
		scene=bpy.context.scene
		
			
		row = layout.row() 
		if len(scene.cam_operations)==0:
			layout.label('Add operation first')
		if len(scene.cam_operations)>0:
			ao=scene.cam_operations[scene.cam_active_operation]
			if ao.valid: 
				layout.prop(ao,'optimize')
				if ao.optimize:
					layout.prop(ao,'optimize_threshold')
				if ao.geometry_source=='OBJECT' or ao.geometry_source=='GROUP':
					exclude_exact= ao.strategy=='CUTOUT' or ao.strategy=='DRILL' or ao.strategy=='PENCIL'
					if not exclude_exact:
						layout.prop(ao,'use_exact')
					#if not ao.use_exact or:
					layout.prop(ao,'pixsize')
					layout.prop(ao,'imgres_limit')
					
					sx=ao.max.x-ao.min.x
					sy=ao.max.y-ao.min.y
					resx=int(sx/ao.pixsize)
					resy=int(sy/ao.pixsize)
					l='resolution:'+str(resx)+'x'+str(resy)
					layout.label( l)
					
				layout.prop(ao,'simulation_detail')
				layout.prop(ao,'circle_detail')
				#if not ao.use_exact:#this will be replaced with groups of objects.
				#layout.prop(ao,'render_all')# replaced with groups support
		
class CAM_AREA_Panel(CAMButtonsPanel, bpy.types.Panel):
	"""CAM operation area panel"""
	bl_label = "CAM operation area "
	bl_idname = "WORLD_PT_CAM_OPERATION_AREA"
	
	COMPAT_ENGINES = {'BLENDERCAM_RENDER'}
	

	def draw(self, context):
		layout = self.layout
		scene=bpy.context.scene
		row = layout.row() 
		if len(scene.cam_operations)==0:
			layout.label('Add operation first')
		if len(scene.cam_operations)>0:
			ao=scene.cam_operations[scene.cam_active_operation]
			if ao.valid:
				#o=bpy.data.objects[ao.object_name]
				layout.prop(ao,'use_layers')
				if ao.use_layers:
					layout.prop(ao,'stepdown')
				
				layout.prop(ao,'ambient_behaviour')
				if ao.ambient_behaviour=='AROUND':
					layout.prop(ao,'ambient_radius')
				
				layout.prop(ao,'maxz')#experimental
				if ao.geometry_source=='OBJECT' or ao.geometry_source=='GROUP':
					layout.prop(ao,'minz_from_ob')
					if not ao.minz_from_ob:
						layout.prop(ao,'minz')
				else:
					layout.prop(ao,'source_image_scale_z') 
					layout.prop(ao,'source_image_size_x') 
					if ao.source_image_name!='':
						i=bpy.data.images[ao.source_image_name]
						if i!=None:
							sy=int((ao.source_image_size_x/i.size[0])*i.size[1]*1000000)/1000
							layout.label('image size on y axis: '+ str(sy)+getUnit())
							#print(dir(layout))
							layout.separator()
					layout.prop(ao,'source_image_offset') 
					col = layout.column(align=True)
					#col.label('image crop:')
					#col=layout.column()
					col.prop(ao,'source_image_crop',text='Crop source image') 
					if ao.source_image_crop:
						col.prop(ao,'source_image_crop_start_x',text='start x') 
						col.prop(ao,'source_image_crop_start_y',text='start y') 
						col.prop(ao,'source_image_crop_end_x',text='end x')
						col.prop(ao,'source_image_crop_end_y',text='end y')
				layout.prop(ao,'use_limit_curve')				   
				if ao.use_limit_curve:
					layout.prop_search(ao, "limit_curve", bpy.data, "objects")
				layout.prop(ao,"ambient_cutter_restrict")
				
class CAM_PACK_Panel(CAMButtonsPanel, bpy.types.Panel):	 
	"""CAM material panel"""
	bl_label = "Pack curves on sheet"
	bl_idname = "WORLD_PT_CAM_PACK"
		
	COMPAT_ENGINES = {'BLENDERCAM_RENDER'}
	
	def draw(self, context):
		layout = self.layout
		scene=bpy.context.scene
		settings=scene.cam_pack
		layout.label('warning - algorithm is slow.' )
		layout.label('only for curves now.' )
		
		layout.operator("object.cam_pack_objects")
		layout.prop(settings,'sheet_fill_direction')
		layout.prop(settings,'sheet_x')
		layout.prop(settings,'sheet_y')
		layout.prop(settings,'distance')
		layout.prop(settings,'rotate')

		
class CAM_SLICE_Panel(CAMButtonsPanel, bpy.types.Panel):	 
	"""CAM slicer panel"""
	bl_label = "Slice model to plywood sheets"
	bl_idname = "WORLD_PT_CAM_SLICE"
		
	COMPAT_ENGINES = {'BLENDERCAM_RENDER'}
	
	def draw(self, context):
		layout = self.layout
		scene=bpy.context.scene
		settings=scene.cam_slice
		
		layout.operator("object.cam_slice_objects")
		layout.prop(settings,'slice_distance')
		layout.prop(settings,'indexes')