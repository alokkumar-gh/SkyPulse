# SkyPulse Operational & Database Scripts

This directory houses database seeding, partition management, and synthetic stream generation utilities:
- `create_partitions.py`: PostgreSQL monthly table partition generator
- `seed_locations.py`: Indian geospatial administrative boundary seeding
- `compute_adjacency.py`: PostGIS ST_Touches spatial neighbor precomputation for DWEG
- `seed_demo.py`: Pre-seeded historical weather events across India
- `generate_stream.py`: Live synthetic weather report generator
