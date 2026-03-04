variable "project_id" {
  description = "ID du projet Scaleway"
  type        = string
}



variable "region" {
  description = "Région Scaleway (ex: fr-par, nl-ams, pl-waw)"
  type        = string
  default     = "nl-ams"
}

variable "zone" {
  description = "Zone pour les Security Groups/Instances (ex: fr-par-1)"
  type        = string
  default     = "nl-ams-1"
}

variable "vpc_name" {
  description = "Nom du VPC"
  type        = string
  default     = "vpc-main"
}

variable "name_prefix" {
  description = "Préfixe commun pour nommer les ressources réseau"
  type        = string
  default     = "corp"
}

variable "tags" {
  description = "Tags à poser sur les ressources réseau"
  type        = list(string)
  default     = []
}

variable "subnets" {
  description = <<EOT
Map <nom -> CIDR> des segments à créer (1 Private Network par entrée).
Par défaut: public, app, data.
EOT
  type = map(string)
  default = {
    public = "10.42.0.0/24"
    app    = "10.42.1.0/24"
    data   = "10.42.2.0/24"
  }
}

variable "mgmt_cidrs" {
  description = "CIDR(s) autorisés pour SSH (22/TCP) et WireGuard (51820/UDP)"
  type        = list(string)
  default     = ["203.0.113.5/32"]
}

variable "sg_name" {
  description = "Nom du Security Group"
  type        = string
  default     = "sg-network"
}

variable "sg_outbound_policy" {
  description = "Politique par défaut en sortie (accept|drop)"
  type        = string
  default     = "accept"
}

variable "extra_inbound_rules" {
  description = "Règles inbound supplémentaires (si besoin)"
  type = list(object({
    protocol  = string
    port      = number
    ip_range  = string
    action    = optional(string)
  }))
  default = []
}
