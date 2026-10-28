"""Loads burner key in-process only from env. Never prints/logs/writes the key."""
import os,json,urllib.request
from solders.keypair import Keypair
RPC="https://api.mainnet-beta.solana.com"
def keypair():return Keypair.from_base58_string(os.environ["SOLANA_BURNER_PRIVATE_KEY"])
def rpc(method,params):
    r=urllib.request.Request(RPC,json.dumps({"jsonrpc":"2.0","id":1,"method":method,"params":params}).encode(),{"Content-Type":"application/json"})
    return json.loads(urllib.request.urlopen(r,timeout=20).read())
def sol_balance(pub):return rpc("getBalance",[pub])["result"]["value"]/1e9
if __name__=="__main__":
    pub=str(keypair().pubkey());b=sol_balance(pub)
    px=json.loads(urllib.request.urlopen("https://lite-api.jup.ag/price/v3?ids=So11111111111111111111111111111111111111112",timeout=20).read())
    p=list(px.values())[0]["usdPrice"]
    print(pub,b,"SOL","~$%.2f"%(b*p),"SOL/USD",p)
