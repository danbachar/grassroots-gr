package input;

import core.*;
import interfaces.BluetoothInterface;
import java.util.*;
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
      fromHost.purgeMessageBuffer();
      toHost.purgeMessageBuffer();
    }
  }

  static {
    DTNSim.registerForReset(StaticHostMessageGenerator.class.getCanonicalName());
    reset();
  }

  public static void reset() {
    pairs = null;
  }

  public StaticHostMessageGenerator(Settings s) {
    super(s);
    this.countPerPair = s.getInt(COUNT_PER_PAIR_S);
    this.mode = Mode.getByValue(s.getInt(MODE_S));
  }

  @Override
  public ExternalEvent nextEvent() {
    if (this.firstRun) {
      var hosts = SimScenario.getInstance().getHosts();
      pairs = new ArrayList<>();
      
      // Create COUNT messages for each valid host pair
      for (DTNHost fromHost : hosts) {
        for (DTNHost toHost : hosts) {
          if (fromHost != toHost) {
            // Check if this pair is valid for the current mode
            BluetoothInterface fromInterface = (BluetoothInterface) fromHost.getInterface(1);
            BluetoothInterface toInterface = (BluetoothInterface) toHost.getInterface(1);

            boolean isValidPair = fromInterface.canConnect(toInterface);
            if (isValidPair) {
              pairs.add(new HostPair(fromHost, toHost, this.countPerPair));
            }
          }
        }
      }
      
      System.out.println("Generated " + pairs.size() + " messages for " + 
                        (this.mode == Mode.INTER_CLUSTER ? "INTER" : "INTRA") + 
                        " cluster mode with " + this.countPerPair + " messages per host pair");
      
      this.firstRun = false;
    }

    // Check if we have any messages left to send
    var selectedPair = pairs.stream()
        .filter(pair -> pair.count > 0)
        .findAny();

    if (selectedPair.isEmpty()) {
      SimScenario.getInstance().getWorld().cancelSim();
      this.nextEventsTime = Double.MAX_VALUE;
      return new ExternalEvent(this.nextEventsTime);
    }

    var pair = selectedPair.get();

    int from = pair.fromHost.getAddress();
    int to = pair.toHost.getAddress();
    int msgSize = drawMessageSize();
    int interval = drawNextEventTimeDiff();
    int newCount = pair.decrementCount();
    if (newCount <= 0) {
      pair.purgeMessageBuffers();
      pairs.remove(pair);
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
