package input;

import core.DTNHost;
import core.DTNSim;
import core.Settings;
import core.SimScenario;
import java.util.Arrays;

public class ActiveHostMessageGenerator
    extends SingleMessageGenerator {
  public static final String COUNT_PER_DISTANCE_S = "count";
  public static final String BIN_SIZE_S = "binSize";
  public static final String MAX_DISTANCE_S = "maxDistance";
  protected final int countPerDistance;
  protected final int binSize;
  protected final int maxDistance;
  protected static int[] distanceBins = null;

  static {
    DTNSim.registerForReset(ActiveHostMessageGenerator.class.getCanonicalName());
    reset();
  }

  public static void reset() {
    distanceBins = null;
  }

  public ActiveHostMessageGenerator(Settings s) {
    super(s);
    this.countPerDistance = s.getInt(COUNT_PER_DISTANCE_S);
    this.binSize = s.getInt(BIN_SIZE_S);
    this.maxDistance = s.getInt(MAX_DISTANCE_S);
    distanceBins = new int[this.maxDistance / this.binSize];
  }

  @Override
  public ExternalEvent nextEvent() {
    int responseSize = 0; /* zero stands for one way messages */
    int msgSize;
    int interval;
    int pollingInterval = 1;
    int from;
    int to;

    boolean hasNonFullBin = Arrays.stream(distanceBins).anyMatch(bin -> bin < this.countPerDistance);
    if (!hasNonFullBin) {
      this.nextEventsTime = Double.MAX_VALUE;
      return new ExternalEvent(this.nextEventsTime);
    }

    /* Get two *different* nodes randomly from the host ranges */
    from = drawHostAddress(this.hostRange);
    to = drawToAddress(hostRange, from);

    msgSize = drawMessageSize();
    interval = drawNextEventTimeDiff();

    /* Create event and advance to next event */
    // Create a dummy event if there are no active hosts
    if (from == -1 || to == -1) {
      this.nextEventsTime += pollingInterval;
      return new ExternalEvent(this.nextEventsTime);
    }

    MessageCreateEvent mce = new MessageCreateEvent(from, to, this.getID(),
        msgSize, responseSize, this.nextEventsTime);
    this.nextEventsTime += interval;

    if (this.msgTime != null && this.nextEventsTime > this.msgTime[1]) {
      /* next event would be later than the end time */
      this.nextEventsTime = Double.MAX_VALUE;
    }

    return mce;
  }

  @Override
  protected int drawHostAddress(int[] hostRange) {
    boolean isActive, hasHostInAvailableBins = false;
    int hostID;
    var hosts = SimScenario.getInstance().getHosts();
    var hasEnoughActiveHosts = hosts.stream().filter(DTNHost::isMovementActive).count() >= 2;
    if (!hasEnoughActiveHosts) {
       return -1; // no active nodes available for message transfer: we need two active distinct hosts
    }
    do {
      hostID = super.drawHostAddress(hostRange);
      int finalHostID = hostID; // for lambda expression
      // if we drew a host that does not exist, the user has supplied a wrong range
      var host = hosts.parallelStream().filter(h -> h.getAddress() == finalHostID).findFirst().orElseThrow();
      isActive = host.isMovementActive();

      if (isActive) {
        var otherActiveHostsInRange = hosts.parallelStream().filter(h -> h.getAddress() != finalHostID && h.isMovementActive() && h.getLocation().distance(host.getLocation()) < this.maxDistance).toList();
        hasHostInAvailableBins = otherActiveHostsInRange
          .stream()
          .anyMatch(h -> {
            int distance = (int)Math.round(host.getLocation().distance(h.getLocation()));
            int indexInBin = Math.floorDiv(distance, this.binSize);
            return distanceBins[indexInBin] < this.countPerDistance;
          });
      }
    } while (!isActive && !hasHostInAvailableBins);

    return hostID;
  }

  @Override
  protected int drawToAddress(int[] hostRange, int from) {

    boolean isActive;
    int hostID;
    var hosts = SimScenario.getInstance().getHosts();
    var fromHost = hosts.stream().filter(h -> h.getAddress() == from).findFirst().orElseThrow();
    var hasEnoughActiveHostsInRange = hosts.stream().filter(h -> h.isMovementActive() && h.getLocation().distance(fromHost.getLocation()) < this.maxDistance).count() >= 2;
    if (!hasEnoughActiveHostsInRange) {
        return -1; // no active nodes available for message transfer: we need two active distinct hosts
    }
    boolean binNeedsMore;
    int indexInBin;
    do {
      hostID = super.drawToAddress(hostRange, from);
      int finalHostID = hostID; // for lambda expression
      // if we drew a host that does not exist, the user has supplied a wrong range
      var toHost = hosts.parallelStream().filter(h -> h.getAddress() == finalHostID).findFirst().orElseThrow();
      isActive = toHost.isMovementActive();

      int distance = (int)Math.round(fromHost.getLocation().distance(toHost.getLocation()));
      indexInBin = Math.floorDiv(distance, this.binSize);
      binNeedsMore = distanceBins[indexInBin] < this.countPerDistance;
    } while (!isActive && !binNeedsMore);

    distanceBins[indexInBin]++;

    return hostID;
  }
}
