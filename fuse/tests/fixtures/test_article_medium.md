# Distributed Systems and Consensus Algorithms

Distributed systems coordinate multiple computers to achieve shared goals while handling failures gracefully. Consensus algorithms ensure all nodes agree on system state despite network partitions and node failures.

## The CAP Theorem

The CAP theorem states that distributed systems can provide at most two of three guarantees:

1. **Consistency**: All nodes see the same data simultaneously
2. **Availability**: Every request receives a response
3. **Partition Tolerance**: System continues despite network failures

Modern systems must choose their trade-offs based on requirements.

## Popular Consensus Algorithms

### Paxos

Paxos was the first proven consensus algorithm. It uses a prepare-accept protocol where proposers coordinate with acceptors to reach agreement. While theoretically elegant, Paxos is notoriously difficult to implement correctly.

### Raft

Raft was designed as an understandable alternative to Paxos. It uses leader election and log replication. The leader receives all client requests and replicates entries to followers. If the leader fails, followers elect a new leader.

### Byzantine Fault Tolerance

Byzantine fault tolerant systems handle nodes that behave maliciously or arbitrarily. PBFT (Practical Byzantine Fault Tolerance) requires 3f+1 nodes to tolerate f faulty nodes.

## Real-World Applications

- **etcd**: Uses Raft for Kubernetes configuration
- **ZooKeeper**: Uses Zab (similar to Paxos) for coordination
- **CockroachDB**: Uses Raft for distributed SQL

Understanding consensus is essential for building reliable distributed systems.
