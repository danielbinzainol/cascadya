###############################################################
# VARIABLES
###############################################################

variable "instance_name" {
  description = "Nom de l'instance Scaleway"
  type        = string
}

variable "instance_type" {
  description = "Type de l'instance (ex : DEV1-S, DEV1-M)"
  type        = string
}

variable "image" {
  description = "Image système utilisée"
  type        = string
  default     = "ubuntu_jammy"
}

variable "zone" {
  description = "Zone Scaleway"
  type        = string
  default     = "nl-ams-1"
}

variable "data_volume_size_gb" {
  description = "Taille du disque de données (en Go)"
  type        = number
  default     = 10
}
variable "security_group_id" {
  description = "ID du security group à attacher à l'instance"
  type        = string
  default     = null
}
variable "private_network_id" {
  description = "ID du réseau privé à attacher à l'instance"
  type        = string
  default     = null
}
variable "user_data" {
  description = "Cloud-init configuration"
  type        = any
  default     = null
}
