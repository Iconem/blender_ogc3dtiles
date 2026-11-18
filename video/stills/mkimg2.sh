#!/bin/bash
cd $TEMP/ogc_tests/r9
D=$(git rev-parse --show-toplevel)/docs/img
S=slides_shots
j() {  # src dst [crop] [bg]
  local f="scale=1600:-2:flags=lanczos"; [ -n "$3" ] && f="crop=$3,$f"
  ffmpeg -v error -y -f lavfi -i color=c=0x${4:-f7f7f7}:s=1920x1080 -i "$1" -filter_complex "[1]scale=1920:1080[s];[0][s]overlay=shortest=1,$f" -frames:v 1 -q:v 4 "$D/$2"
}
j $S/nd_north_tiles.png tiles_random_google.jpg
j $S/venice_solid.png solid_venice.jpg
j $S/sacre_colour.png points_sacre_colour.jpg
j out/r_int_orbit_cy/f_0040.png splats_baldacchino.jpg
j $S/nd_north_cycles.png origin_notre_dame.jpg 1520:855:400:110
j $S/tokyo_cycles.png origin_tokyo.jpg
j $S/colosseum3d_cycles.png origin_colosseum.jpg
j $S/canyon_cycles.png origin_grand_canyon.jpg
j $S/lod_out_outside.png lod_outside_render.jpg "" 3a3a3a
j $S/geghard_cut_colour.png points_geghard.jpg
j $S/geghard_cut_reveal.png points_reveal.jpg
j $S/ign_edl.png beauty_edl_ign.jpg
j $S/ign_beauty.png beauty_ign.jpg
j $S/lod_out_view.png lod_camera_render.jpg
j $S/bayon_shade_relit.png shader_relit.jpg
j $S/ign_class.png lidar_classes_ign.jpg
j $S/ign_edl.png lidar_classes_edl_ign.jpg
j $S/bayon_edl_edl.png shader_albedo.jpg
j $S/geghard_cut_cut.png clip_geghard.jpg
j $S/gizeh_fit_matcap_normal.png mesh_gizeh_normal.jpg
