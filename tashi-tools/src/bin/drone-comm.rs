use std::io::{self, BufRead};
use std::str::{FromStr, from_utf8};

use anyhow::anyhow;
use clap::Parser;
use tashi_vertex::{
    Context, Engine, KeyPublic, KeySecret, Message, Options, Peers, Socket, Transaction,
};
use tokio::sync::mpsc;

#[derive(Debug, Clone)]
struct PeerArg {
    pub address: String,
    pub public: KeyPublic,
}

impl FromStr for PeerArg {
    type Err = anyhow::Error;

    fn from_str(s: &str) -> Result<Self, Self::Err> {
        let (public, address) = s
            .split_once('@')
            .ok_or_else(|| anyhow!("Invalid peer format, expected <public_key>@<address>"))?;

        let public = public.parse()?;
        let address = address.to_string();

        Ok(PeerArg { address, public })
    }
}

#[derive(Debug, Parser)]
#[command(about = "Tashi Vertex drone communication node for Webots")]
struct Args {
    /// Local bind address (e.g., 127.0.0.1:9600)
    #[clap(short = 'B')]
    pub bind: String,

    /// Secret key for this node
    #[clap(short = 'K')]
    pub key: String,

    /// Peer addresses in format <public_key>@<address>
    #[clap(short = 'P')]
    pub peers: Vec<PeerArg>,
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let args = Args::parse();
    let key = args.key.parse::<KeySecret>()?;

    // Initialize peer set
    let mut peers = Peers::with_capacity(args.peers.len())?;

    for peer in &args.peers {
        peers.insert(&peer.address, &peer.public, Default::default())?;
    }

    // Add self to peer set
    peers.insert(&args.bind, &key.public(), Default::default())?;

    // Initialize Tashi Vertex context
    let context = Context::new()?;

    // Bind socket
    let socket = Socket::bind(&context, &args.bind).await?;

    // Configure and start engine
    let mut options = Options::default();
    options.set_report_gossip_events(true);
    options.set_fallen_behind_kick_s(10);

    let engine = Engine::start(&context, socket, options, &key, peers, false)?;

    // Signal ready to Webots controller
    println!("DRONE_COMM_NODE_READY");

    // Channel for stdin messages
    let (tx, mut rx) = mpsc::unbounded_channel::<String>();

    // Stdin reader thread
    std::thread::spawn(move || {
        let stdin = io::stdin();
        for line in stdin.lock().lines() {
            if let Ok(line) = line {
                if !line.is_empty() {
                    let _ = tx.send(line);
                }
            }
        }
    });

    loop {
        tokio::select! {
            result = engine.recv_message() => {
                match result? {
                    Some(Message::Event(event)) => {
                        for tx in event.transactions() {
                            if let Ok(tx_s) = from_utf8(&tx) {
                                println!("RX_TX:{}", tx_s.trim_end_matches('\0'));
                            }
                        }
                    }
                    Some(Message::SyncPoint(_)) => {}
                    None => break,
                }
            }
            Some(msg) = rx.recv() => {
                send_transaction(&engine, &msg)?;
            }
        }
    }

    Ok(())
}

fn send_transaction(engine: &Engine, s: &str) -> tashi_vertex::Result<()> {
    let mut transaction = Transaction::allocate(s.len() + 1);
    transaction[..s.len()].copy_from_slice(s.as_bytes());
    transaction[s.len()] = 0;
    engine.send_transaction(transaction)
}
