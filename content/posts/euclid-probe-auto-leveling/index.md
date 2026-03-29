+++
title = "Klipper教程——自动调平：Euclid Probe组装和配置"
date = 2023-11-21
description = "自动调平能极大提高3D打印的效果，本教程旨在介绍如何给Klipper加入Euclid Probe调平功能。"
categories = ["3D打印", "教程"]
tags = ["Euclid Probe", "Klipper", "自动调平", "教程"]
+++

自动调平能极大提高3D打印的效果，本教程旨在介绍如何给Klipper加入Euclid Probe调平功能。

## 什么是自动调平

自动调平是指在每次打印前，利用bltouch、klicky等开源的调平模组，自动检测不同位置喷头与打印床间距离，通过调整打印床的高度来实现平整的打印表面，得到完美首层，能提高打印成功率，优化打印效果。

### 自动调平原理

自动调平工作过程主要是通过软件控制Z轴往复运动，调平模组的探头在多组X、Y点重复接触，记录下每次触发时的高度。高度的平均值就是模组探头与打印床的距离，在减去设置好的探头与热端喷头的高度差，即可得出打印床不同位置与喷头的距离。

### 为什么要用自动调平

目前3D打印机使用的热床一般为铝基板热床，在热床升温过程中，热胀冷缩会使热床不同位置的表面形变程度不同，导致不同位置的热床高度不一致，尤其是当热床面积大于300x300时甚至会带来毫米级的高度差，严重影响首层打印。

自动调平是目前解决打印床表面平整度差的最佳方案之一。利用自动调平得出的床网参数，可以在打印机X、Y轴运动时，Z轴协同运动，保持喷头与打印床始终为一相对固定距离，这成为了大尺寸打印机必备功能。

与手动调平相比，自动调平能减少很多工作量，只需保持打印床是一个相对平整的表面即可，再也不用蹲在地上拧好久了。

### 为什么要用klicky调平

之前用的是国产的bltouch，一个40块钱，重复精度太差，甚至能导致超过0.1mm的误差，导致哪怕使用自动调平，首层打印效果依然很差。

与bltouch相比，klicky调平有着成本低、稳定性高、重复精度好的特点。在精度测试中，我自己DIY的klicky，最大样本差不超过0.05mm。配合床网补偿功能，能提供一个较好的首层打印效果。

## Euclid Klicky组装

**注意：短接PCB上NC点，不要短接NO点，否则Klipper无法判断探针是否取下！**

博主自制了5套，每套均价5元左右，也可以直接从海鲜市场购买成品或套件，价格在10元至20元不等。

所需配件

- 自行打印的零件，共3个  
　　本人使用的是适配大鱼cc的fz打印头（[项目地址](https://github.com/FZaii/FZburner-CC)或者[点击此处](https://github.com/FZaii/FZburner-CC/releases/download/v1.61/FZburner-CC_ver1.61.rar)直接下载），3个模型文件均在7C_Euclid文件夹内，直接打印即可，不需要支撑。  
　　Euclid Probe官方[项目链接](https://euclidprobe.github.io/)，打印文件[下载](https://github.com/nionio6915/Euclid_Probe/tree/main/stls)链接，自行打印适配打印机的模型文件。
- PCB，嘉立创免费打样，0元
- 微动，欧姆龙微动，2.8元/个
- 3P母座XH2.54，2.96元/20个
- M2*5沉头螺丝，1元/100个
- 6x3沉孔磁铁，0.21元/个，一套需要4个
- M3*10螺丝，2个
- M3六角螺母，1个
- M3型材螺母，1个
- XH2.54连接线，1根
- （可选）510R电阻，0402
- （可选）LED，0402

焊接过程很简单，只需要按照PCB上的标识焊接即可，如图是我焊接的成品。

![](https://blog.mrliu1024.top/wp-content/uploads/2023/11/image-13-1024x768.png)

## Klipper配置

在[printer.cfg]中加入以下内容

```ini
#引入euclid.cfg
[include euclid.cfg]

#启用强制移动
[force_move]
enable_force_move: True

#指定响应类型和方法
[respond]
default_type: echo
default_prefix: echo:
```

在Klipper配置文件中新建euclid.cfg，填入以下内容

```ini
## 以下是示例配置，旨在指导您为自己的打印机配置 Euclid 探头。
##
## 将此配置与您的配置相结合时，请确保所有注释标记都以"@TODO "开头。 否则可能会损坏你的探针、打印机或你的自尊心。
##
##
## 本示例适用于固定基座、固定龙门/车架和移动床运动系统，如 RailCore、Ender5、V-Core3 等。Delta 打印机也类似
##
## 像 Voron 这样的移动龙门式打印机需要进行一些调整，以确保适当的间隙和水平程序；下面提供了一些提示。
##
## 阵列变量的实现和宏设置归功于 Brian Lalor，他是 Discord 上的 yolo-dubstep#8033。有关更新和详情，请参阅 https://github.com/blalor/vcore3-ratos-config。
##
## @TODO 以下是硬件配置的硬件探针配置。它可以出现在 printer.cfg 中，也可以出现在 euclid.cfg 中，但不能同时出现。
##更多详情，请参阅 https://euclidprobe.github.io/05_klipper.html。

#[probe]
## Euclid 探针在 Huvud 板上的引脚 ?? 上
#pin: !PE5
##y_offset: -27.5
#z_offset: 7.5
#speed: 5
#samples: 2
#samples_result: median
#sample_retract_dist: 5.0
#samples_tolerance: 0.05
#samples_tolerance_retries: 3
#lift_speed: 30


[gcode_macro EuclidProbe]
description: 查看Euclid probe挂载和归位的配置变量

## @TODO 替换坐标以适应您的打印机
variable_position_preflight: [  150, 30 ] # 工作准备位置
variable_position_side:      [  207, 30 ] # 挂载准备位置
variable_position_dock:      [  207, 0  ] # 停靠坞的坐标
## @TODO 如果您的打印机有固定的Z限位，请在此处定义
## @TODO 例如 Voron Trident
variable_position_zstop:     [ 150,250 ] #Z限位的位置

## 归位准备位置
variable_position_exit:      [ 150 , 0 ] #归位位置

## 工具头与打印床间高度差
variable_bed_clearance: 15

## probe dock height
## @TODO 如果工具头可以相对于测头基座高度垂直移动（例如连接到 Voron 2.4 等龙门架打印机上），则将其设置为测头基座的 Z 位置。
# variable_dock_height: 15

##移动速度mm/min
variable_move_speeds: 18000

## 内部状态变量；不用于配置！
variable_batch_mode_enabled: False
variable_probe_state: None

gcode:
	RESPOND TYPE=command MSG="{ printer['gcode_macro EuclidProbe'] }"

#归位是针对特定机器的。  
#本例适用于龙门架/移动床打印机，如 Rat Rig V-Core 3
#确保只在 Klipper 配置的一个位置（通常在此处或 printer.cfg）定义 [homing_override]
#尤其重要的是，在尝试将 Z 轴归位之前，要确保探头已挂载
#[homing_override]
#axes: z
#set_position_z: -5
#gcode:
#    {% set euclid_probe = printer["gcode_macro EuclidProbe"] %}
#
#    G90
#
#    # 强制打印床和工具头分离
#    SET_KINEMATIC_POSITION Z=0
#    G0 Z{ euclid_probe.bed_clearance } F500
#
#    # 强制X、Y轴归位，X轴先归位来保证不会撞到停靠坞
#
#    {% if "x" not in (printer.toolhead.homed_axes | lower) %}
#        G28 X
#    {% endif %}
#
#    {% if "y" not in (printer.toolhead.homed_axes | lower) %}
#        G28 Y
#    {% endif %}

	## 如果你打算将探针作为Z轴限位，请先挂载探针
	## 如果你在使用固定的停靠坞，请注释掉下一行
	#DEPLOY_PROBE

	##将探头移动到打印床中心，归位Z轴
	#G0 X{ printer.toolhead.axis_maximum.x/2 } Y{ printer.toolhead.axis_maximum.y/2 } F{ euclid_probe.move_speeds }
	#G28 Z



	##Z轴归位后，探头将与打印床接触，此处将Z轴抬起
	#G0 Z{euclid_probe.bed_clearance} F500

	## 如果你使用虚拟限位，请将探针归位
	## 如果你使用固定限位，请注释掉下一行
	#STOW_PROBE


[gcode_macro _ASSERT_PROBE_STATE]
description:确保探针处于已知状态；QUERY_PROBE 必须在此宏之前被调用过！
gcode:
	## QUERY_PROBE是探针状态
	## "TRIGGERED" -> 1 :: 探针已归位
	## "open"      -> 0 :: 探针已挂载
	QUERY_PROBE
    
	{% set last_query_state = "stowed" if printer.probe.last_query == 1 else "deployed" %}

	{% if params.MUST_BE != last_query_state %}
		{ action_raise_error("expected probe state to be {} but is {} ({})".format(params.MUST_BE, last_query_state, printer.probe.last_query)) }
	{% else %}
		## 工作正常；更新状态
		SET_GCODE_VARIABLE MACRO=EuclidProbe VARIABLE=probe_state VALUE="'{ last_query_state }'"
	{% endif %}


[gcode_macro ASSERT_PROBE_DEPLOYED]
description: 报错如果探针未挂载
gcode:
	# 等待移动完成，并暂停0.25秒  
	M400
	G4 P250

	QUERY_PROBE
	_ASSERT_PROBE_STATE MUST_BE=deployed


[gcode_macro ASSERT_PROBE_STOWED]
description: 报错如果探针没归位
gcode:
	# 等待移动完成，并暂停0.25秒    
	M400
	G4 P250

	QUERY_PROBE
	_ASSERT_PROBE_STATE MUST_BE=stowed


[gcode_macro EUCLID_PROBE_BEGIN_BATCH]
description: 开启 Euclid 探针批量测量模式
gcode:
	SET_GCODE_VARIABLE MACRO=EuclidProbe VARIABLE=batch_mode_enabled VALUE=True
	RESPOND TYPE=command MSG="Probe batch mode enabled"


[gcode_macro EUCLID_PROBE_END_BATCH]
description: 结束 Euclid 探针批量测量模式并归位探针
gcode:
	SET_GCODE_VARIABLE MACRO=EuclidProbe VARIABLE=batch_mode_enabled VALUE=False
	RESPOND TYPE=command MSG="Probe batch mode disabled"
	STOW_PROBE


[gcode_macro DEPLOY_PROBE]
description: 挂载探针
gcode:
	{% set euclid_probe = printer["gcode_macro EuclidProbe"] %}

	{% if euclid_probe.batch_mode_enabled and euclid_probe.probe_state == "deployed" %}
		RESPOND TYPE=command MSG="Probe batch mode enabled: already deployed"
	{% else %}
		RESPOND TYPE=command MSG="Deploying probe"

		# 保证探针当前未挂载
		ASSERT_PROBE_STOWED

		G90

		# 提升高度，避免挤出头与打印床干涉
		G0 Z{ euclid_probe.bed_clearance } F500

		# 将工具头移至安全位置，开始挂载
		G0 X{ euclid_probe.position_preflight[0] } Y{ euclid_probe.position_preflight[1] } F{ euclid_probe.move_speeds }

		#  移动到停靠坞旁
		G0 X{ euclid_probe.position_side[0] } Y{ euclid_probe.position_side[1] } F{ euclid_probe.move_speeds }

		# @TODO 固定床停靠和移动龙门打印机需要在此处添加移动命令，以将龙门降低到停靠高度
		# G0 Z {euclid_probe.dock_height} F500

		# 等待0.25秒
		M400
		G4 P250

		#  挂载探针
		G0 X{ euclid_probe.position_dock[0] } Y{ euclid_probe.position_dock[1] } F1500

		# 确认挂在成功
		ASSERT_PROBE_DEPLOYED

		# 直线移出停靠坞
		G0 X{ euclid_probe.position_exit[0] } Y{ euclid_probe.position_exit[1] } F{ euclid_probe.move_speeds }
	{% endif %}


[gcode_macro STOW_PROBE]
description: 将 Euclid 探针归位
gcode:
	{% set euclid_probe = printer["gcode_macro EuclidProbe"] %}

	{% if euclid_probe.batch_mode_enabled %}
		RESPOND TYPE=command MSG="Probe batch mode enabled: not stowing"
	{% else %}
		RESPOND TYPE=command MSG="正在将探针归位"

		# 确保探针没有挂载
		ASSERT_PROBE_DEPLOYED

		G90

		# 设置固定龙门系统的接近高度，以清除床上的探头
		G0 Z{ euclid_probe.bed_clearance } F3000

		# @TODO 固定床底座和移动龙门打印机需要在此处添加移动命令以降低龙门到底座的高度
		# G0 Z{euclid_probe.dock_height} F500

		# 移动到归位准备位置
		G0 X{ euclid_probe.position_exit[0] } Y{ euclid_probe.position_exit[1] } F{ euclid_probe.move_speeds }

		# 慢慢移动进停靠坞
		G0 X{ euclid_probe.position_dock[0] } Y{ euclid_probe.position_dock[1] } F3000

		#移动完成后等待0.25秒
		M400
		G4 P250

		# 移动到停靠坞侧面
		G0 X{ euclid_probe.position_side[0] } Y{ euclid_probe.position_side[1] } F{ euclid_probe.move_speeds }

		# 检测探针是否成功归位
		ASSERT_PROBE_STOWED
	{% endif %}


## 简单示例：通过在前后包裹 DEPLOY_PROBE/STOW_PROBE 宏来执行一次 BED_MESH_CALIBRATE（床网标定）。
## 如果需要更复杂的示例（只对将要打印的区域进行探测），可参考：https://github.com/blalor/vcore3-ratos-config/blob/50e757ec32e085bedb3b9fa317581f9aa1913dd2/euclid.cfg#L230-L305
[gcode_macro BED_MESH_CALIBRATE]
rename_existing: BED_MESH_CALIBRATE_ORIG
gcode:
	DEPLOY_PROBE
	BED_MESH_CALIBRATE_ORIG
	STOW_PROBE


## @TODO 如有需要，请按自己的机器情况取消注释下面其中一个宏：
## * Z_TILT_ADJUST 适用于 [z_tilt] 配置（Z 轴多点调平）
## * QUAD_GANTRY_LEVEL 适用于 [quad_gantry_level] 配置（龙门四角调平）

# [gcode_macro Z_TILT_ADJUST]
# description: 修改后的 Z_TILT_ADJUST，前后包裹了 DEPLOY_PROBE/STOW_PROBE 宏
# rename_existing: Z_TILT_ADJUST_ORIG
# gcode:
#     DEPLOY_PROBE
#     Z_TILT_ADJUST_ORIG
#     STOW_PROBE


## @TODO 确认在 [quad_gantry_level] 配置中 horizontal_move_z 的抬升高度足够，避免探针或喷嘴刮到打印件
# [gcode_macro QUAD_GANTRY_LEVEL]
# description: 修改后的 QUAD_GANTRY_LEVEL，前后包裹了 DEPLOY_PROBE/STOW_PROBE 宏
# rename_existing: QUAD_GANTRY_LEVEL_ORIGINIAL
# gcode:
#     DEPLOY_PROBE
#     QUAD_GANTRY_LEVEL_ORIGINIAL
#     STOW_PROBE


[gcode_macro PROBE_CALIBRATE]
rename_existing: PROBE_CALIBRATE_ORIG
gcode:
	{% set euclid_probe = printer["gcode_macro EuclidProbe"] %}
	DEPLOY_PROBE

	G90
	G0 X{ printer.toolhead.axis_maximum.x/2 } Y{ printer.toolhead.axis_maximum.y/2 } F{ euclid_probe.move_speeds }

	M117 Beginning probe calibration; remove probe before measuring nozzle height!
	PROBE_CALIBRATE_ORIG

# 下面是从切片软件中调用 START_PRINT 的示例起始 G-code（例如在 PrusaSlicer 中）：
# START_PRINT EXTRUDER_TEMP=[first_layer_temperature] BED_TEMP=[first_layer_bed_temperature] FILAMENT_TYPE=[filament_type]
[gcode_macro START_PRINT]
gcode:
	{% set extruder_temp = params.EXTRUDER_TEMP | default(printer.extruder.target, true) %}
	{% set bed_temp      = params.BED_TEMP      | default(printer.heater_bed.target, true) %}

	## 将各种状态重置为配置或安全默认设置
	CLEAR_PAUSE

	# 重置速度和挤出率，以防手动更改
	M220 S100
	M221 S100

	# 使用公制单位（毫米等）
	G21

	# 使用绝对位置
	G90

	# 将挤出机设置为绝对位置模式
	M82

	EUCLID_PROBE_BEGIN_BATCH

	# 回零位
	G28

	# 等待热床加热
	M117 Heating bed...
	M190 S{ bed_temp }

	# @TODO 如果打印机需要，可启用床面倾斜调整。
	# * Z_TILT_ADJUST 用于 [z_tilt] 配置（Z 轴倾斜校正）
	# * QUAD_GANTRY_LEVEL 用于 [quad_gantry_level] 配置（龙门四点调平）

	# M117 Adjusting for tilt...（提示：正在进行倾斜校正）
	# Z_TILT_ADJUST

	# M117 Performing gantry leveling...（提示：正在进行龙门调平）
	# QUAD_GANTRY_LEVEL

	# 再次归零，因为在调整和加热床铺后，Z 会发生变化。
	M117 Rehoming after leveling...
	G28 Z

	BED_MESH_CALIBRATE

	EUCLID_PROBE_END_BATCH

	# 等待挤出机加热
	M109 S{ extruder_temp }

	M117 Printing...

	M83
	G92 E0
```

写入完成后保存并重启，即可在控制台中看到与自动调平有关的宏。

## 在切片软件中启用自动调平

### 手动开启自动调平（不推荐）

如果觉得在每次打印前都进行调平很费时，那可以只在需要的时候自动调平，只需要在切片软件起始Gcode中加入`BED_MESH_PROFILE LOAD=default`，即可在每次打印前载入已有床网数据进行调平。

### 每次打印前自动调平（推荐）

在printer.cfg或euclid.cfg中加入以下内容，启用G29宏：

```ini
[gcode_macro G29]
gcode:
 G28
 BED_MESH_CALIBRATE
 BED_MESH_PROFILE SAVE=myprofit
 G28
```

在切片软件起始Gcode中加入G29，即可在每次打印前进行自动调平操作。
