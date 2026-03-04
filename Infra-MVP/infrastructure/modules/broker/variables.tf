variable "name" {
  type        = string
  default     = "vm-broker"
}

variable "instance_type" {
  type        = string
  default     = "DEV1-S"
}

variable "zone" {
  type        = string
}

variable "private_network_id" {
  type        = string
}

variable "security_group_id" {
  type        = string
}
variable "user_data" {
  type = map(string)
}
