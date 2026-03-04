###############################################################
# VARIABLES - Module ThingsBoard DB
###############################################################

variable "region" {
  description = "Région Scaleway (ex: nl-ams)"
  type        = string
}

variable "private_network_id" {
  description = "ID du réseau privé à attacher à la base"
  type        = string
}

variable "node_type" {
  description = "Type d’instance pour la base PostgreSQL managée"
  type        = string
  default     = "DB-DEV-M"
}

variable "db_user" {
  description = "Nom d’utilisateur de la base"
  type        = string
  default     = "thingsboard"
}

variable "db_password" {
  description = "Mot de passe de la base"
  type        = string
  default     = "ChangeMe123!"
  sensitive   = true
}

variable "db_name" {
  description = "Nom de la base ThingsBoard"
  type        = string
  default     = "thingsboard"
}

variable "db_size_gb" {
  description = "Taille du volume de la base (Go)"
  type        = number
  default     = 20
}
