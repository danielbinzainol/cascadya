###############################################################
# Data Lake - Setup Environnement Data (4.7)
###############################################################

# Bucket Object Storage (Scaleway S3)
resource "scaleway_object_bucket" "data_lake" {
  name   = "data-lake-thingsboard-dev"
  region = local.scw_region

  tags = {
    terraform   = "true"
    data_lake   = "true"
    thingsboard = "true"
    export      = "true"
  }
}

# Sortie Terraform
output "data_lake_bucket_name" {
  description = "Nom du bucket S3 du Data Lake"
  value       = scaleway_object_bucket.data_lake.name
}
