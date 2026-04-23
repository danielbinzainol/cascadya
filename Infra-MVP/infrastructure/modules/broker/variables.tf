variable "name" {
  type        = string
  default     = "broker-DEV1-S"
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
