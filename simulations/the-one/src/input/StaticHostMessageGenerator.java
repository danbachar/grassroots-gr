package input;

import core.*;
import interfaces.BluetoothInterface;
import java.util.*;
import movement.RandomStationaryCluster;
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
      toHost.purgeMessageBuffer(fromHost);
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
        BluetoothInterface fromInterface = (BluetoothInterface) fromHost.getInterface(1);
        int nodeDegree = fromInterface.getMaxDegree();

        for (DTNHost toHost : hosts2) {
          if (nodeDegree == 0) {
            // not really accurate because this should be bidirectional but still better
            continue;
          }
          if (fromHost != toHost) {
            // Check if this pair is valid for the current mode
            boolean isValidPair = (this.mode == Mode.INTER_CLUSTER) || 
                                 (((RandomStationaryCluster) fromHost.getMovementModel()).isInSameCluster(toHost));
            if (isValidPair) {
              nodeDegree--;
              pairs.add(new HostPair(fromHost, toHost, this.countPerPair));
            }
          }
        }
      }
      
      System.out.println("Generated " + pairs.size()*this.countPerPair + (this.mode == Mode.INTER_CLUSTER ? " inter" : " intra ") + "cluster messages for " + pairs.size() + " pairs");

      this.firstRun = false;
      pairIterator = pairs.iterator();
    }

    // Find next pair with remaining messages
    HostPair pair = null;
    while (pairIterator.hasNext()) {
      HostPair candidate = pairIterator.next();
      if (candidate.count > 0) {
        pair = candidate;
        break;
      }
    }

    if (pair == null) {
      SimScenario.getInstance().getWorld().cancelSim();
      this.nextEventsTime = Double.MAX_VALUE;
      return new ExternalEvent(this.nextEventsTime);
    }

    int from = pair.fromHost.getAddress();
    int to = pair.toHost.getAddress();
    int msgSize = drawMessageSize();
    int interval = drawNextEventTimeDiff();
    int newCount = pair.decrementCount();
    
    // No need to remove - just let the iterator skip exhausted pairs
    if (newCount <= 0) {
      pair.purgeMessageBuffers();
    }

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
