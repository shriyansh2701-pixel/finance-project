provider "aws" {
    region = "us-east-1"
}

# 1. Open the Firewall for Streamlit (8501) and SSH (22)
resource "aws_security_group" "ai_sg" {
    name        = "ai_app_security"
    description = "Allow web traffic to our AI app"

    ingress {
        from_port   = 8501
        to_port     = 8501
        protocol    = "tcp"
        cidr_blocks = ["0.0.0.0/0"]
    } 

    ingress {
        from_port   = 22
        to_port     = 22
        protocol    = "tcp"
        cidr_blocks = ["0.0.0.0/0"]
    } 

    egress {
        from_port   = 0
        to_port     = 0
        protocol    = "-1"
        cidr_blocks = ["0.0.0.0/0"]
    }
}

# 2. Rent the Server and give it a Startup Script
resource "aws_instance" "ai_server" {
    ami            = "ami-0c7217cdde317cfec" # Ubuntu 22.04
    instance_type  = "t2.micro" # Free tier eligible!
    vpc_security_group_ids = [aws_security_group.ai_sg.id]

    # This script runs the moment the server turns on
    user_data = <<-EOF
                #!/bin/bash
                sudo apt-get update -y
                sudo apt-get install docker.io git -y
                sudo systemctl start docker
                sudo systemctl enable docker
                
                # Download your code from GitHub and run it!
                # IMPORTANT: Replace the URL below with YOUR actual GitHub repository link
                git clone https://github.com/YourUsername/finance-project.git
                cd finance-project
                sudo docker build -t ai-agent .
                sudo docker run -d -p 8501:8501 ai-agent
                EOF

    tags = {
        Name = "AI-Inbox-Manager"
    }              
}