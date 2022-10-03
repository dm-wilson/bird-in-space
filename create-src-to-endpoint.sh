#! /bin/bash

# create a table of all object positions - 
curl -H "Authorization: Bearer ${TB_RW_TOKEN}" \
    -XPOST "https://api.tinybird.co/v0/datasources" \
    -d "format=ndjson" \
    --data-urlencode """schema=satnum \`json:$.satnum\` String,
            name \`json:$.name\` String,
            time \`json:$.time\` DateTime64(3, 'UTC'),
            e_lat \`json:$.e_lat\`  Float32,
            e_lng \`json:$.e_lng\`  Float32,
            e_alt \`json:$.e_alt\`  Float32,
            d_x \`json:$.d_x\`  Float32,
            d_y \`json:$.d_y\`  Float32,
            d_z \`json:$.d_z\`  Float32
    """ \
    -d "engine=ReplacingMergeTree" \
    -d "engine_ver=time"\
    -d "engine_sorting_key=satnum" \
    -d "name=astro_obj_positions"

# only a simple pipe needed to format for API
curl -H "Authorization: Bearer ${TB_RW_TOKEN}" \
	-X POST https://api.tinybird.co/v0/pipes \
	-d """name=recent_astro_obj_positions&sql=SELECT 
      name, 
      time, 
      (e_lat, e_lng) as earth_position,
      e_alt as altitude,
      (d_x, d_y, d_z) as vel_vector
    FROM astro_obj_positions FINAL
    WHERE time > now() - 600
    """

curl -X POST -H "Authorization: Bearer ${TB_RW_TOKEN}" \
    "https://api.tinybird.co/v0/pipes/recent_astro_obj_positions/nodes/recent_astro_obj_positions_0/endpoint"