package input;

import core.*;
import java.util.*;
import movement.RandomStationaryCluster;
public class StaticHostMessageGenerator
    extends SingleMessageGenerator {
  public static final String COUNT_PER_PAIR_S = "count";
  public static final String MODE_S = "mode";
  protected final int countPerPair;
  protected final Mode mode;

  protected boolean firstRun = true;
  protected static Queue<HostPair> messageQueue = null;

  public enum Mode {
    INTRA_CLUSTER,
    INTER_CLUSTER;

    public static Mode getByValue(int value){
      return Arrays.stream(Mode.values()).filter(e -> e.ordinal() == value).findFirst().orElse(INTRA_CLUSTER);
    }

  }

  private record HostPair(DTNHost fromHost, DTNHost toHost) {}

  static {
    DTNSim.registerForReset(StaticHostMessageGenerator.class.getCanonicalName());
    reset();
  }

  public static void reset() {
    messageQueue = null;
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
      messageQueue = new LinkedList<>();
      
      // Create COUNT messages for each valid host pair
      for (DTNHost fromHost : hosts) {
        for (DTNHost toHost : hosts) {
          if (fromHost != toHost) {
            // Check if this pair is valid for the current mode
            boolean isValidPair = (this.mode == Mode.INTER_CLUSTER) || 
                                 (((RandomStationaryCluster) fromHost.getMovementModel()).isInSameCluster(toHost));
            
            if (isValidPair) {
              for (int i = 0; i < this.countPerPair; i++) {
                messageQueue.add(new HostPair(fromHost, toHost));
              }
            }
          }
        }
      }
      
      System.out.println("Generated " + messageQueue.size() + " messages for " + 
                        (this.mode == Mode.INTER_CLUSTER ? "INTER" : "INTRA") + 
                        " cluster mode with " + this.countPerPair + " messages per host pair");
      
      this.firstRun = false;
    }

    // Check if we have any messages left to send
    if (messageQueue.isEmpty()) {
      SimScenario.getInstance().getWorld().cancelSim();
      this.nextEventsTime = Double.MAX_VALUE;
      return new ExternalEvent(this.nextEventsTime);
    }

    HostPair selectedPair = messageQueue.poll();
    
    int from = selectedPair.fromHost.getAddress();
    int to = selectedPair.toHost.getAddress();
    int msgSize = drawMessageSize();
    int interval = drawNextEventTimeDiff();
    int responseSize = 0; /* zero stands for one way messages */

    MessageCreateEvent mce = new MessageCreateEvent(from, to, this.getID(),
        msgSize, responseSize, this.nextEventsTime);
    this.nextEventsTime += interval;

    if (this.msgTime != null && this.nextEventsTime > this.msgTime[1]) {
      /* next event would be later than the end time */
      this.nextEventsTime = Double.MAX_VALUE;
    }

    return mce;
}
}
