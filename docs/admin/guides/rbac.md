# Configure Role Based Access Control

!!! warning
    This feature is a Tech Preview and may be subject to change.


!!! note
    User `admin` automatically gets all RBAC permissions.


RPM plugin presents Role Based Access for these endpoints :

- RPM Alternate Content Source (`/pulp/api/v3/acs/rpm/rpm/`)
- RPM Distributions (`/pulp/api/v3/distributions/rpm/rpm/`)
- RPM Publications (`/pulp/api/v3/publications/rpm/rpm/`)
- RPM Remotes (`/pulp/api/v3/remotes/rpm/rpm/` and `/pulp/api/v3/remotes/rpm/uln`)
- RPM Repository (`/pulp/api/v3/repositories/rpm/rpm/`)
- RPM Copy (`/pulp/api/v3/rpm/copy/`)

!!! note
    Content is secured too, but the only condition right now is the authenticated user.


## Default Roles

RPM plugin ships a few default roles described bellow.

### Viewer Role

This role contains only `view` permission for an endpoint. Using this permission you can control who can
view specific content for example a repository.

=== "Check a Role"

    ```shell
     pulp role show --name "rpm.rpmremote_viewer"
    ```

=== "Output"

    ```json
    {
      "pulp_href": "/pulp/api/v3/roles/62baf888-09c2-4c18-8d3a-354d9c6bdb48/",
      "pulp_created": "2022-04-07T12:41:11.065567Z",
      "name": "rpm.rpmremote_viewer",
      "description": null,
      "permissions": [
        "rpm.view_rpmremote"
      ],
      "locked": true
    }
    ```

### Creator Role

This role contains only `add` permission for a specific endpoint to allow a user to create a new object of its type.
Be aware that you may need additional permission to create a new object.
For example, `rpm.rpmrepository_view` is needed for a used repository to create a new publication.

```json title="Example of the requested condition to create an RPM Publication"
 {
     "action": ["create"],
     "principal": "authenticated",
     "effect": "allow",
     "condition": [
         "has_model_perms:rpm.add_rpmpublication",
         "has_repo_attr_model_or_obj_perms:rpm.view_rpmrepository",
     ]
 }
```

### Owner Role

This role contains all permissions needed for manipulating objects, such as modifying or removing them.
This role also contains permission to manage role assignments on the object,
for example, adding or removing user roles.

By default, the user who created a new object will receive this role.

```json title="Example of the RPM Remote owner role"
 {
   "pulp_href": "/pulp/api/v3/roles/592356da-8cdf-4a1b-a434-3f10cda285f7/",
   "pulp_created": "2022-04-07T12:41:11.047168Z",
   "name": "rpm.rpmremote_owner",
   "description": null,
   "permissions": [
     "rpm.change_rpmremote",
     "rpm.delete_rpmremote",
     "rpm.manage_roles_rpmremote",
     "rpm.view_rpmremote"
   ],
   "locked": true
 }
```

## RPM specific Roles

Also, the RPM plugin ships two roles to use.

### RPM Admin Role (rpm.admin)

This role is like a pulp admin but only for the RPM plugin -
it can perform any RPM workflow with no restrictions. If you need a more
specific admin role as a repo maintainer, you need to combine
permissions on your own. More in the `Creating Roles` section.

```json title="rpm.admin role"
 {
   "pulp_href": "/pulp/api/v3/roles/08d16dda-038b-4fbb-b3fc-acb081111e6a/",
   "pulp_created": "2022-04-07T12:41:11.129526Z",
   "name": "rpm.admin",
   "description": null,
   "permissions": [
      "rpm.add_rpmalternatecontentsource",
      "rpm.add_rpmdistribution",
      "rpm.add_rpmpublication",
      "rpm.add_rpmremote",
      "rpm.add_rpmrepository",
      "rpm.add_ulnremote",
      "rpm.change_rpmalternatecontentsource",
      "rpm.change_rpmdistribution",
      "rpm.change_rpmremote",
      "rpm.change_rpmrepository",
      "rpm.change_ulnremote",
      "rpm.delete_rpmalternatecontentsource",
      "rpm.delete_rpmdistribution",
      "rpm.delete_rpmpublication",
      "rpm.delete_rpmremote",
      "rpm.delete_rpmrepository",
      "rpm.delete_rpmrepository_version",
      "rpm.delete_ulnremote",
      "rpm.manage_roles_rpmalternatecontentsource",
      "rpm.manage_roles_rpmdistribution",
      "rpm.manage_roles_rpmpublication",
      "rpm.manage_roles_rpmremote",
      "rpm.manage_roles_rpmrepository",
      "rpm.manage_roles_ulnremote",
      "rpm.modify_content_rpmrepository",
      "rpm.refresh_rpmalternatecontentsource",
      "rpm.repair_rpmrepository",
      "rpm.sync_rpmrepository",
      "rpm.view_rpmalternatecontentsource",
      "rpm.view_rpmdistribution",
      "rpm.view_rpmpublication",
      "rpm.view_rpmremote",
      "rpm.view_rpmrepository",
      "rpm.view_ulnremote",
   ],
   "locked": true
 }
```

!!! note
    Please note there are two types of Remotes with their individual permissions.


### RPM Viewer Role (rpm.viewer)

A universal role allows you to view all content within the RPM plugin.

```json title="Universal RPM viewer role"
 {
   "pulp_href": "/pulp/api/v3/roles/d1e7bae0-2363-45e2-815c-d721ecc3133c/",
   "pulp_created": "2022-04-07T12:41:11.144883Z",
   "name": "rpm.viewer",
   "description": null,
   "permissions": [
     "rpm.view_rpmalternatecontentsource",
     "rpm.view_rpmdistribution",
     "rpm.view_rpmpublication",
     "rpm.view_rpmremote",
     "rpm.view_rpmrepository",
     "rpm.view_ulnremote",
   ],
   "locked": true
 }
```

#### Content and RepositoryVersions Permissions

RPM Content and RepositoryVersions are unique as they do not have any default roles on their
viewsets. Content's access policy allows any authenticated user to create content, however
they must specify the repository to upload to since viewing content is scoped by the repositories
the user has permission for. RepositoryVersions' access policy requires the user to have
permissions on the parent repository in order to perform actions on the repository version. Both
objects have CRD permissions in the database that can be assigned to users, but currently their
access policies do not use them for authorization.

## Creating Roles

!!! note
    Roles shipped by the RPM plugin mentioned above are locked and cannot be modified or removed.


To create a new role, you need to specify its name and permissions to use.
To find out which permissions you need for a new role, you can list an endpoints policy with the following command:

=== "List endpoint access-policies"

    ```shell
     pulp access-policy show --viewset-name "repositories/rpm/rpm"
    ```

=== "Output"

    ```json
    {
      "pulp_href": "/pulp/api/v3/access_policies/dae50330-83b5-4ab0-b74f-f54e1d2cbf29/",
      "pulp_created": "2022-04-25T15:27:48.556140Z",
      "permissions_assignment": [
        {
          "function": "add_roles_for_object_creator",
          "parameters": {
            "roles": "rpm.rpmrepository_owner"
          }
        }
      ],
      "creation_hooks": [
        {
          "function": "add_roles_for_object_creator",
          "parameters": {
            "roles": "rpm.rpmrepository_owner"
          }
        }
      ],
      "statements": [
        {
          "action": [
            "list",
            "my_permissions"
          ],
          "effect": "allow",
          "principal": [
            "authenticated"
          ]
        },
        {
          "action": [
            "retrieve"
          ],
          "effect": "allow",
          "condition": "has_model_or_obj_perms:rpm.view_rpmrepository",
          "principal": "authenticated"
        },
        {
          "action": [
            "create"
          ],
          "effect": "allow",
          "condition": [
            "has_remote_param_model_or_obj_perms:rpm.view_rpmremote",
            "has_model_perms:rpm.add_rpmrepository"
          ],
          "principal": "authenticated"
        },
        {
          "action": [
            "update",
            "partial_update"
          ],
          "effect": "allow",
          "condition": [
            "has_model_or_obj_perms:rpm.change_rpmrepository",
            "has_model_or_obj_perms:rpm.view_rpmrepository",
            "has_remote_param_model_or_obj_perms:rpm.view_rpmremote"
          ],
          "principal": "authenticated"
        },
        {
          "action": [
            "modify"
          ],
          "effect": "allow",
          "condition": [
            "has_model_or_obj_perms:rpm.modify_content_rpmrepository",
            "has_model_or_obj_perms:rpm.view_rpmrepository"
          ],
          "principal": "authenticated"
        },
        {
          "action": [
            "destroy"
          ],
          "effect": "allow",
          "condition": [
            "has_model_or_obj_perms:rpm.delete_rpmrepository",
            "has_model_or_obj_perms:rpm.view_rpmrepository"
          ],
          "principal": "authenticated"
        },
        {
          "action": [
            "sync"
          ],
          "effect": "allow",
          "condition": [
            "has_model_or_obj_perms:rpm.sync_rpmrepository",
            "has_model_or_obj_perms:rpm.view_rpmrepository",
            "has_remote_param_model_or_obj_perms:rpm.view_rpmremote"
          ],
          "principal": "authenticated"
        },
        {
          "action": [
            "list_roles",
            "add_role",
            "remove_role"
          ],
          "effect": "allow",
          "condition": "has_model_or_obj_perms:rpm.manage_roles_rpmrepository",
          "principal": "authenticated"
        }
      ],
      "viewset_name": "repositories/rpm/rpm",
      "customized": false
    }
    ```

**Example 1: RPM Repository Creator**

```shell title="Example of the RPM repository creator role"
 pulp role create --name "rpm_repo_creator" \
     --permission "rpm.add_rpmrepository" \
     --permission "rpm.view_rpmrepository" \
     --permission "rpm.sync_rpmrepository" \
     --permission "rpm.modify_rpmrepository" \
     --permission "rpm.change_rpmrepository" \
     --permission "rpm.delete_rpmrepository" \
     --permission "rpm.add_rpmremote" \
     --permission "rpm.change_rpmremote" \
     --permission "rpm.delete_rpmremote" \
     --permission "rpm.view_rpmremote"
```

**Example 2: RPM Publisher**

```shell title="Example of the RPM publisher role"
 pulp role create --name "rpm_publisher" \
     --permission "rpm.view_rpmrepository" \
     --permission "rpm.add_rpmpublication" \
     --permission "rpm.add_rpmdistribution"
```

```shell title="Globally assign these roles to user"
 pulp user role-assignment add --username "bob" --role "rpm_repo_creator" --object ""
 pulp user role-assignment add --username "jack" --role "rpm_publisher" --object ""
```

!!! note
    You can only assign roles at the object level if the role contains at least one permission applicable for that object.


## Edit Access Policy

It is possible to edit the `access policy` for an endpoint.

```shell title="Change the access policy of all actions not requiring any permission."
pulp access-policy update \
     --viewset-name "remotes/rpm/rpm" \
     --statements '[{"action": ["list", "retrieve"], "effect": "allow"}, {"action": "*", "effect": "allow"}]'
```

!!! warning
    When editing access policies, you must specify all the endpoint actions, or their usage will lead to failure.


You can modify `creation-hooks` to specify what will happen after object creation.
By default, a user will receive the `owner` role.

```shell title="Update creation hook of a repository to creator gets another role than `repository_owner`"
pulp access-policy update --viewset-name "repositories/rpm/rpm" \
     --creation-hooks '[{"function": "add_roles", "parameters": {"roles": "rpm_viewer"}}]'
```

Of course, you can reset the access policy back to the default with the command:

```shell
pulp access-policy reset --viewset-name "repositories/rpm/rpm"
```
