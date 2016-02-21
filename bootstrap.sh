sudo apt-get update
cd /home/
sudo wget https://3230d63b5fc54e62148e-c95ac804525aac4b6dba79b00b39d1d3.ssl.cf1.rackcdn.com/Anaconda3-2.5.0-Linux-x86_64.sh
bash /home/Anaconda3-2.5.0-Linux-x86_64.sh -b -p /home/anaconda
export PATH="/home/anaconda/bin:$PATH"
conda create -n UberHackathon -y python==3.4.3 pip
source activate UberHackathon
pip install flask
pip install requests
# export PATH="$HOME/anaconda/bin:$PATH"
# conda create -n UberHackathon -y python==3.4.3 pip
# source activate UberHackathon
# pip install flask
# pip install requests