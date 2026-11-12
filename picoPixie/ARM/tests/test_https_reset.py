from pathlib import Path
s=(Path(__file__).resolve().parents[1]/"src"/"cloud_https.cpp").read_text()
start=s[s.index("bool CloudHttps::start("):s.index("void CloudHttps::dns_callback")]
assert "clear_exchange();" in start
assert start.index("clear_exchange();") < start.index("policy_.start(now)")
assert "expected_fen_=fen;" in start
assert "chess_response_matches_fen(body,expected_fen_)" in s
assert "std::string().swap(received_);" in s
assert "result_=CloudResult{};" in s
print("Fresh HTTPS exchange and FEN binding: OK")
