#! /usr/bin/bash

if [ -d ~/.bashrc.d ]; then
  for file in ~/.bashrc.d/*; do
    . "$file"
  done
fi

git checkout 3.13.3
prestart

pulp rpm remote create --name=on_demand_broken --url=https://fixtures.pulpproject.org/rpm-unsigned/ --policy=on_demand
pulp rpm repository create --name=on_demand_broken --remote=on_demand_broken
pulp rpm repository sync --name=on_demand_broken
pulp rpm publication create --repository=on_demand_broken
PUBLICATION_HREF=$(pulp rpm publication list | jq -r .[0].pulp_href)
pulp rpm distribution create --name=on_demand_broken --publication=$PUBLICATION_HREF --base_url=on_demand_broken

pulp rpm remote create --name=immediate_broken --url=https://download1.rpmfusion.org/free/fedora/releases/33/Everything/x86_64/os/
pulp rpm repository create --name=immediate_broken --remote=immediate_broken
pulp rpm repository sync --name=immediate_broken

git checkout 3.14
prestart

pulp rpm remote create --name=immdiate_ok --url=https://download1.rpmfusion.org/free/fedora/releases/32/Everything/x86_64/os/
pulp rpm repository create --name=immediate_ok --remote=immdiate_ok
pulp rpm repository sync --name=immediate_ok
pulp rpm publication create --repository=immediate_ok
