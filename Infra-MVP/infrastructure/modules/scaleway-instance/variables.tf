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
  description = "Image systeme utilisee"
  type        = string
  default     = "ubuntu_jammy"
}

variable "zone" {
  description = "Zone Scaleway"
  type        = string
  default     = "nl-ams-1"
}

variable "data_volume_size_gb" {
  description = "Taille du disque de donnees (en Go)"
  type        = number
  default     = 10
}

variable "root_volume_size_gb" {
  description = "Taille du disque systeme (en Go)"
  type        = number
  default     = null
}

variable "security_group_id" {
  description = "ID du security group a attacher a l'instance"
  type        = string
  default     = null
}

variable "private_network_id" {
  description = "ID du reseau prive a attacher a l'instance"
  type        = string
  default     = null
}

variable "user_data" {
  description = "Cloud-init configuration"
  type        = any
  default     = null
}

variable "tags" {
  description = "Tags explicites de l'instance"
  type        = list(string)
  default     = null
}

variable "protected" {
  description = "Protection contre la suppression accidentelle"
  type        = bool
  default     = false
}
