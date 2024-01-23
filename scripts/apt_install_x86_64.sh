#!/bin/bash

set -ex

sudo yum update -y
sudo yum install java-1.8.0-openjdk.x86_64 -y
java -version

sudo cp /etc/profile /etc/profile_backup
echo export JAVA_HOME=/usr/lib/jvm/jre-1.8.0-openjdk | sudo tee -a /etc/profile
echo export JRE_HOME=/usr/lib/jvm/jre | sudo tee -a /etc/profile
source /etc/profile

# download android sdk
sudo curl https://dl.google.com/android/repository/sdk-tools-linux-3859397.zip -o android-sdk.zip
# install unzip command
sudo apt-get install unzip OR sudo yum install unzip
# unzip into this folder
sudo unzip android-sdk.zip -d .
# remove the zip file
sudo rm android-sdk.zip

sudo ./tools/bin/sdkmanager "tools"
sudo ./tools/bin/sdkmanager --list
sudo ./tools/bin/sdkmanager --licenses
