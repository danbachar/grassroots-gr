/*
 * Copyright 2010 Aalto University, ComNet
 * Released under GPLv3. See LICENSE.txt for details.
 */
package core;

/**
 * A chunk of a message that is created at a node or passed between nodes.
 */
public class MessageChunk {
	public final int chunkSize;
	public final Message originalMessage;
	public final double timeCreated;
	private double timeReceived;
	private final int chunkIndex;

	static {
		reset();
		DTNSim.registerForReset(MessageChunk.class.getCanonicalName());
	}

	/**
	 * Creates a new chunk of a message.
	 * @param m the original message
	 * @param size chunk size
	 */
	public MessageChunk(Message m, int size, int chunkIndex) {
		this.originalMessage = m;
		this.chunkSize = size;
		this.timeCreated = SimClock.getTime();
		this.timeReceived = -1;
		this.chunkIndex = chunkIndex;
	}

	/**
	 * Sets the time when this message was received.
	 * @param time The time to set
	 */
	public void setTimeReceived(double time) {
		this.timeReceived = time;
	}

	/**
	 * Returns the time when this message was received
	 * @return The time
	 */
	public double getTimeReceived() {
		return this.timeReceived;
	}

	public int getChunkIndex() {
		return this.chunkIndex;
	}
	/**
	 * Resets all static fields to default values
	 */
	public static void reset() {
		// TODO
	}
}
