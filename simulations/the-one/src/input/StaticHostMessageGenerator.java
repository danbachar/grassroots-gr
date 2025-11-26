package input;

import core.*;
import movement.RandomStationaryCluster;

import java.util.*;
import java.util.stream.Collectors;

public class StaticHostMessageGenerator
    extends SingleMessageGenerator {
  /**
  * Number of messages sent between every host pair -setting id ({@value} ).
  */
  public static final String COUNT_PER_PAIR_S = "count";

  /**
  * Number of messages sent between every host pair -setting id ({@value} ).
  */
  public static final String MODE_S = "mode";

  private final int countPerPair;
  private final Mode mode;

  private boolean firstRun = true;
  private static List<HostPair> pairs = null;
  private static Iterator<HostPair> pairIterator = null;
  public static int deliveredMessages = 0;
  public static int totalMessages = 0;

  public enum Mode {
    INTRA_CLUSTER,
    INTER_CLUSTER;

    public static Mode getByValue(int value){
      return Arrays.stream(Mode.values()).filter(e -> e.ordinal() == value).findFirst().orElse(INTRA_CLUSTER);
    }

  }

  private class HostPair {
    public final DTNHost fromHost;
    public final DTNHost toHost;
    public int count;
    public HostPair(DTNHost fromHost, DTNHost toHost, int count) {
      this.fromHost = fromHost;
      this.toHost = toHost;
      this.count = count;
    }

    public int decrementCount() {
      return --this.count;
    }

    public void purgeMessageBuffers() {
      fromHost.purgeMessageBuffer(toHost);
      toHost.purgeMessageBuffer(fromHost); // TODO: is this needed? maybe this is purging messages we dont need to purge?
    }
  }

  static {
    DTNSim.registerForReset(StaticHostMessageGenerator.class.getCanonicalName());
    reset();
  }

  public static void reset() {
    pairs = null;
    pairIterator = null;
  }

  public StaticHostMessageGenerator(Settings s) {
    super(s);
    this.countPerPair = s.getInt(COUNT_PER_PAIR_S);
    this.mode = Mode.getByValue(s.getInt(MODE_S));
  }

  // Find next pair with remaining messages
  private Optional<HostPair> getNextMessagingPair() {
    while (pairIterator.hasNext()) {
        HostPair candidate = pairIterator.next();
        if (candidate.count > 0) {
            return Optional.of(candidate);
        }
    }

    return Optional.empty();
  }

  @Override
  public ExternalEvent nextEvent() {
    if (this.firstRun) {
      var hosts1 = new ArrayList<>(SimScenario.getInstance().getHosts());
      Collections.shuffle(hosts1);

      var hosts2 = new ArrayList<>(SimScenario.getInstance().getHosts());
      Collections.shuffle(hosts2);
      
      pairs = new ArrayList<>();
      
      // Create COUNT messages for each valid host pair
      for (DTNHost fromHost : hosts1) {
        for (DTNHost toHost : hosts2) {
          if (fromHost != toHost) {
            // Check if this pair is valid for the current mode
            boolean isValidPair = (this.mode == Mode.INTER_CLUSTER) ||
                                 (((RandomStationaryCluster) fromHost.getMovementModel()).isInSameCluster(toHost));
            if (isValidPair) {
              pairs.add(new HostPair(fromHost, toHost, this.countPerPair));
            }
          }
        }
      }

      if (pairs.isEmpty()) {
        SimScenario.getInstance().getWorld().cancelSim();
        this.nextEventsTime = Double.MAX_VALUE;
        return new ExternalEvent(this.nextEventsTime);
      }
      totalMessages = pairs.size() * this.countPerPair;
      System.out.println("Generated " + totalMessages + (this.mode == Mode.INTER_CLUSTER ? " inter" : " intra ") + "cluster messages for " + pairs.size() + " pairs");

      this.firstRun = false;
      pairIterator = pairs.iterator();
    }

    // iterator will iterate on the entire list, once it reaches the end it will go back to start if there are more messages to send
    // if end is reached and no more messages, stop simulation
    Optional<HostPair> currentMessagingPair = getNextMessagingPair();
    if (currentMessagingPair.isEmpty()) {
      boolean hasMoreMessagesToSend = pairs.stream().anyMatch(p -> p.count > 0);
      if (hasMoreMessagesToSend) {
        // go back to start, shuffle order
        pairs = pairs.stream().filter(p -> p.count > 0).collect(Collectors.toList());
        Collections.shuffle(pairs);
        pairIterator = pairs.iterator();
        currentMessagingPair = getNextMessagingPair();
      }
    }

    boolean finishedAllMessages = totalMessages == deliveredMessages;
    if (currentMessagingPair.isEmpty() || finishedAllMessages) {
      if (finishedAllMessages) {
        // we only cancel if all messages have been delivered; otherwise there are more messages cruising around waiting to be delivered
        SimScenario.getInstance().getWorld().cancelSim();
      }
      this.nextEventsTime = Double.MAX_VALUE;
      return new ExternalEvent(this.nextEventsTime);
    }

    var pair = currentMessagingPair.get();
    int from = pair.fromHost.getAddress();
    int to = pair.toHost.getAddress();
    int msgSize = drawMessageSize();
    int interval = drawNextEventTimeDiff();
    pair.decrementCount();

    MessageCreateEvent mce = new MessageCreateEvent(from, to, this.getID(),
        msgSize, 0, this.nextEventsTime);
    this.nextEventsTime += interval;

    if (this.msgTime != null && this.nextEventsTime > this.msgTime[1]) {
      /* next event would be later than the end time */
      this.nextEventsTime = Double.MAX_VALUE;
    }

    return mce;
  }
}
