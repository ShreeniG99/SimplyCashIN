from app.channels.simulated import SimulatedChannel


def test_simulated_channel_records_send():
    ch = SimulatedChannel()
    result = ch.send(buyer_id="anand", message="Namaste", channel_kind="WhatsApp Business")
    assert result.ok is True
    assert ch.sent[0]["message"] == "Namaste"
    assert ch.sent[0]["buyer_id"] == "anand"
