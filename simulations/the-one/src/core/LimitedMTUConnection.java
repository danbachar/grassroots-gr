package core;

import routing.MessageRouter;

/**
 * A PDU-limited connection between two DTN nodes. If messages are larger than the PDU, they will be chunked
 */
public class LimitedMTUConnection extends Connection {
	private int msgsize;
	private int msgsent;
	private int currentspeed = 0;
	private double lastUpdate = 0;
	private static final int PATH_MTU = 247; // BLE 4.2+ MTU
	private int fullSizeChunkCount;
	private int lastChunkSize;
	/**
	 * Creates a new connection between nodes and sets the connection
	 * state to "up".
	 * @param fromNode The node that initiated the connection
	 * @param fromInterface The interface that initiated the connection
	 * @param toNode The node in the other side of the connection
	 * @param toInterface The interface in the other side of the connection
	 */
   public LimitedMTUConnection(DTNHost fromNode, NetworkInterface fromInterface,
		   DTNHost toNode, NetworkInterface toInterface) {
	    super(fromNode, fromInterface, toNode, toInterface);
		this.msgsent = 0;
	}

	/**
	 * Sets a message that this connection is currently transferring. If message
	 * passing is controlled by external events, this method is not needed
	 * (but then e.g. {@link #finalizeTransfer()} and
	 * {@link #isMessageTransferred()} will not work either). Only a one message
	 * at a time can be transferred using one connection.
	 * @param from The host sending the message
	 * @param m The message
	 * @return The value returned by
	 * {@link MessageRouter#receiveMessage(Message, DTNHost)}
	 */
	@Override
	public int startTransfer(DTNHost from, Message m) {
		assert this.msgOnFly == null : "Already transferring " +
			this.msgOnFly + " from " + this.msgFromNode + " to " +
			this.getOtherNode(this.msgFromNode) + ". Can't "+
			"start transfer of " + m + " from " + from;

		this.msgFromNode = from;
		Message newMessage = m.replicate();
		int retVal = getOtherNode(from).receiveMessage(newMessage, from);

		if (retVal == MessageRouter.RCV_OK) {
			var rest = newMessage.getSize() % PATH_MTU;
			var hasRest = rest > 0;
			var messageSize = newMessage.getSize();
			var numberOfChunks = messageSize / PATH_MTU;
			for (int i = 0; i < numberOfChunks + (hasRest ? 1 : 0); i++) {
				int chunkSize = i == numberOfChunks ? rest : PATH_MTU;
				if (chunkSize == PATH_MTU) {
					this.fullSizeChunkCount++;
				} else {
					this.lastChunkSize = chunkSize;
				}
			}

			this.msgsize = messageSize;
			this.msgOnFly = newMessage;
		}

		return retVal;
	}

	/**
	 * Calculate the current transmission speed from the information
	 * given by the interfaces, and calculate the missing data amount.
	 *
	 */
	@Override
	public void update() {
		double now = core.SimClock.getTime();
		currentspeed =  this.fromInterface.getTransmitSpeed(toInterface);
		int othspeed =  this.toInterface.getTransmitSpeed(fromInterface);

		if (othspeed < currentspeed) {
			currentspeed = othspeed;
		}
		var theoreticalNumberOfSendableBytesSinceLastUpdate = currentspeed * (now - this.lastUpdate);
		var total = 0;

		// send as many chunks as possible within limit: if cannot send all chunks try sending the last (smaller due to division rest) chunk
		// chunk sending order does not matter as we are only interested in the theoretical limit
		int chunksTaken;
		for (chunksTaken=0; chunksTaken<this.fullSizeChunkCount && (total + PATH_MTU <= theoreticalNumberOfSendableBytesSinceLastUpdate); chunksTaken++) {
			total += PATH_MTU;
		}
		this.fullSizeChunkCount -= chunksTaken;
		if (this.lastChunkSize > 0 && total + this.lastChunkSize <= theoreticalNumberOfSendableBytesSinceLastUpdate) {
			total += this.lastChunkSize;
			this.lastChunkSize = 0;
		}

		this.msgsent += total;
		this.lastUpdate = now;
	}

	/**
	 * returns the current speed of the connection
	 */
	@Override
	public double getSpeed() {
		return this.currentspeed;
	}

    /**
     * Returns the amount of bytes to be transferred before ongoing transfer
     * is ready or 0 if there's no ongoing transfer or it has finished
     * already
     * @return the amount of bytes to be transferred
     */
	@Override
    public int getRemainingByteCount() {
		int bytesLeft = this.msgsize - this.msgsent;
		return Math.max(bytesLeft, 0);
    }

	/**
	 * Returns true if the current message transfer is done.
	 * @return True if the transfer is done, false if not
	 */
	@Override
	public boolean isMessageTransferred() {
        return this.msgsent >= this.msgsize;
	}
}
