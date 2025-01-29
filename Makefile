target/debug/suriano-indexer: src/main.rs ../annorepo_rust_client/src/lib.rs
	@cargo build

.PHONY: run
run: target/debug/suriano-indexer
	@cargo run
