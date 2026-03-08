# Running Odoo with Docker

Everything here is taken from the [Official Odoo Docker Image](https://hub.docker.com/_/odoo)

## TLDR
```bash
docker run -d                           \
    -v odoo-db:/var/lib/postgresql/data \
    -e POSTGRES_USER=odoo               \
    -e POSTGRES_PASSWORD=odoo           \
    -e POSTGRES_DB=postgres             \
    --name db postgres:15
docker run                                              \
    -v odoo-data:/var/lib/odoo                          \
    -v path/to/our/custom_modules:/mnt/extra-addons     \
    -d -p 8069:8069 --name odoo --link db:db -t odoo
```
Then:
```bash
docker stop odoo db
docker start db odoo
```

## Quick Reminder of Docker Stuff
- `-d` detached mode (run the container in the background)
- `-e` set environment variables
- `--name` name our container/instance
- `-v` volume
  - `-v volume_name:path/to/container/mount_point` or `-v path/to/volume/data:path/to/container/mount_point` 
  - `path/to/container/mount_point` is where you mount data for an image, if you have a container `container_name` this path is typically `/var/lib/container_name`
- `-t` terminal/TTY
- The final argument, like `postgres:15` at the end of a `docker run` command is the __Docker Image__
- `docker run` always creates a new container instance from an image

## Running without a volume
1) Create & Run the DB Container/Instance:
```bash 
docker run -d -e POSTGRES_USER=odoo -e POSTGRES_PASSWORD=odoo -e POSTGRES_DB=postgres --name db postgres:15
```
2) Create & Run the Odoo instance, connecting it to the DB instance:
```bash
docker run -p 8069:8069 --name odoo --link db:db -t odoo
```


## Running with a Docker Volume (Better)
If you remove the `odoo` container, the filestore (odoo data) is lost. To prevent this run the container with a **Docker volume**
Likewise, if you remove the `db` container, the DB data is lost.

1) Create and start the DB instance and its named module
```bash
docker run -d -v odoo-db:/var/lib/postgresql/data -e POSTGRES_USER=odoo -e POSTGRES_PASSWORD=odoo -e POSTGRES_DB=postgres --name db postgres:15
```
2) Create and start both the odoo instance and a named volume 
```bash
docker run -v odoo-data:/var/lib/odoo -d -p 8069:8069 --name odoo --link db:db -t odoo
```
3) At this point, everything is created and wired together
4) After, we can just run `docker stop odoo db` or `docker start db odoo` (note the order)

## Running with Custom Modules
We are interested in running Odoo with our own modules.
The Odoo Image expects addons to be mounted at `/mnt/extra-addons`
```bash
docker run -v /path/to/addons:/mnt/extra-addons -p 8069:8069 --name odoo --link db:db -t odoo
```
The problem with this command is that we have to run this, which creates an instance, every time we update our module code.
