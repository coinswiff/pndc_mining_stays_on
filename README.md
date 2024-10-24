# pndc_mining_stays_on
Mining Automation Bot

CAVEAT : your mileage might vary. I made this for my specific screen.  

You should have a mining window open already. Go to pond0x.com, sign in with your wallet and have it so that eth and solana are both connected.

1. Installation
```
poetry install
```

2. Config ( to calculate the offset for the mining window )
NOTE:Copy and paste the miner config output to mining_config.json 

```
poetry run python src/miner_config.py
```
The above command will ask you to click on the window where you are mining to calculate co-ordinates.
Update your miner_config.json with the value printed above

3. Create output screenshot directory for debugging. Periodically delete files 
```
mkdir -p out/screenshots
```

4. Run the bot ( in this case the first bot indicated by index 0 ) 
```
poetry run python src/minepond.py mine_pond 0
```



