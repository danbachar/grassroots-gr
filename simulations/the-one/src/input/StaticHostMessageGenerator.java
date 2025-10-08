package input;

import core.*;
import java.util.*;
import movement.RandomStationaryCluster;
public class StaticHostMessageGenerator
    extends SingleMessageGenerator {
  public static final String COUNT_PER_DISTANCE_S = "count";
  public static final String BIN_SIZE_S = "binSize";
  public static final String MODE_S = "mode";
  protected final int countPerDistance;
  protected final int binSize;
  protected final Mode mode;

  protected boolean firstRun = true;
  protected static List<Integer> binRanges = null;
  protected static List<Bin> binHostPairs = null; // count left per bin, together with host pairs in bin

  public static enum Mode {
    INTRA_CLUSTER,
    INTER_CLUSTER;

    public static final Mode getByValue(int value){
      return Arrays.stream(Mode.values()).filter(e -> e.ordinal() == value).findFirst().orElse(INTRA_CLUSTER);
    }

  }

  private record HostPair(DTNHost fromHost, DTNHost toHost) {}

  protected class Bin {
    int count;
    List<HostPair> pairs;

    protected Bin(int count, List<HostPair> pairs) {
      this.count = count;
      this.pairs = pairs;
    }

    protected void decrementCount() {
      this.count--;
    }
  }

  static {
    DTNSim.registerForReset(StaticHostMessageGenerator.class.getCanonicalName());
    reset();
  }

  public static void reset() {
    binRanges = null;
    binHostPairs = null;
  }

  public StaticHostMessageGenerator(Settings s) {
    super(s);
    this.countPerDistance = s.getInt(COUNT_PER_DISTANCE_S);
    this.binSize = s.getInt(BIN_SIZE_S);
    this.mode = Mode.getByValue(s.getInt(MODE_S));
  }

  @Override
  public ExternalEvent nextEvent() {

    if (this.firstRun) {
      var hosts = SimScenario.getInstance().getHosts();
      var distanceOptions = this.calculateDistanceOptions(hosts);

      // Create bins with width <binSize>, but only for ranges that contain actual distances
      binRanges = this.calculateBinRanges(distanceOptions);
      
      // Create host pairs for each bin
      binHostPairs = new ArrayList<>(binRanges.size());
      binRanges.forEach(b -> binHostPairs.add(new Bin(this.countPerDistance, new ArrayList<>())));
      this.populateHostPairs(hosts);

      this.firstRun = false;
    }

    int responseSize = 0; /* zero stands for one way messages */
    int msgSize;
    int interval;
    int pollingInterval = 1;
    int from;
    int to;

    var possiblyNonEmptyBin = binHostPairs.stream().filter(bin -> bin.count > 0).findAny();
    boolean hasNonFullBin = possiblyNonEmptyBin.isPresent();
    if (!hasNonFullBin) {
      SimScenario.getInstance().getWorld().cancelSim();
      this.nextEventsTime = Double.MAX_VALUE;
      return new ExternalEvent(this.nextEventsTime);
    }

    HostPair selectedPair = drawHostPair();
    if (selectedPair == null) {
      this.nextEventsTime += pollingInterval;
      return new ExternalEvent(this.nextEventsTime);
    }
    
    from = selectedPair.fromHost.getAddress();
    to = selectedPair.toHost.getAddress();

    msgSize = drawMessageSize();
    interval = drawNextEventTimeDiff();

    MessageCreateEvent mce = new MessageCreateEvent(from, to, this.getID(),
        msgSize, responseSize, this.nextEventsTime);
    this.nextEventsTime += interval;

    if (this.msgTime != null && this.nextEventsTime > this.msgTime[1]) {
      /* next event would be later than the end time */
      this.nextEventsTime = Double.MAX_VALUE;
    }

    return mce;
  }

  private HostPair drawHostPair() {
    // randomly pick from available bins
    var possiblyNonEmptyRandomBin = binHostPairs.stream().filter(bin -> bin.count > 0).findAny();
    if (possiblyNonEmptyRandomBin.isEmpty()) {
      return null;
    }
    
    Bin selectedBin = possiblyNonEmptyRandomBin.get();
    
    // randomly pick an available pair from the bin and decrement the counter of more messages needed in the bin
    HostPair selectedPair = selectedBin.pairs.stream().findAny().orElseThrow(); // the throw will only happen if bin has no pairs -> cannot actually happen
    selectedBin.decrementCount();
    
    return selectedPair;
  }

    private List<Integer> calculateDistanceOptions(List<DTNHost> hosts) {
      return hosts.stream()
        .flatMap(h1 -> hosts.stream()
          .filter(h2 -> h1 != h2)
          .filter(h2 -> this.mode == Mode.INTER_CLUSTER || (((RandomStationaryCluster) h1.getMovementModel()).isInSameCluster(h2)))
          .map(h2 -> (int) Math.round(h1.getLocation().distance(h2.getLocation())))
        )
        .distinct()
        .sorted()
        .toList();
    }

    private List<Integer> calculateBinRanges(List<Integer> distanceOptions) {
      return distanceOptions.stream()
          .map(distance -> (distance / this.binSize) * this.binSize) // Floor to nearest bin start
          .distinct()
          .sorted()
          .toList();
    }

    private int findBinIndex(int distance) {
      int binStart = (distance / this.binSize) * this.binSize;
      return binRanges.indexOf(binStart);
    }

    private void populateHostPairs(List<DTNHost> hosts) {
      hosts
      .stream()
      .flatMap(h1 -> hosts.stream()
        .filter(h2 -> h1 != h2)
        .filter(h2 -> this.mode == Mode.INTER_CLUSTER || (((RandomStationaryCluster) h1.getMovementModel()).isInSameCluster(h2)))
        .map(h2 -> new HostPair(h1, h2)))
      .forEach(pair -> {
        int distance = (int) Math.round(pair.fromHost.getLocation().distance(pair.toHost.getLocation()));
        int binIndex = findBinIndex(distance);
        Bin bin = binHostPairs.get(binIndex);
        bin.pairs.add(pair);
        binHostPairs.set(binIndex, bin);
    });
    }
}
