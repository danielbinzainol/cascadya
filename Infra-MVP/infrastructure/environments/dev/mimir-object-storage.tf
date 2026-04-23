locals {
  mimir_bucket_name     = "cascadya-mimir-dev-${substr(replace(local.scw_project_id, "-", ""), 0, 8)}"
  mimir_bucket_endpoint = "https://s3.${local.scw_region}.scw.cloud"
}

resource "scaleway_object_bucket" "mimir" {
  name       = local.mimir_bucket_name
  region     = local.scw_region
  project_id = local.scw_project_id
}

resource "scaleway_object_bucket_acl" "mimir" {
  bucket = scaleway_object_bucket.mimir.name
  acl    = "private"
}
