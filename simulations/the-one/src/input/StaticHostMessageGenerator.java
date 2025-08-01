package input;

import core.*;
import gui.DTNSimGUI;
import java.util.*;

public class StaticHostMessageGenerator
    extends SingleMessageGenerator {
  public static final String COUNT_PER_DISTANCE_S = "count";
  public static final String BIN_SIZE_S = "binSize";
  protected final int countPerDistance;
  protected final int binSize;
  protected boolean firstRun = true;
  protected static List<Integer> binRanges = null;
  protected static List<Bin> binHostPairs = null; // count left per bin, together with host pairs in bin

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
  }

  @Override
  public ExternalEvent nextEvent() {

    if (this.firstRun) {
      var hosts = SimScenario.getInstance().getHosts();
      var distanceOptions = this.calculateDistanceOptions(hosts);

      // Create bins with width <binSize>, but only for ranges that contain actual distances
      binRanges = this.calculateBinRanges(distanceOptions);
      System.out.println("Created " + binRanges.size() + " distance bins:");
      
      // Create host pairs for each bin
      binHostPairs = new ArrayList<>(binRanges.size());
      for (var _: binRanges) {
        binHostPairs.add(new Bin(this.countPerDistance, new ArrayList<>()));
      }
      
      this.populateHostPairs(hosts);

      this.firstRun = false;
    }

    int responseSize = 0; /* zero stands for one way messages */
    int msgSize;
    int interval;
    int pollingInterval = 1;
    int from;
    int to;

    var countNonEmptyBins = binHostPairs.stream().filter(bin -> bin.count > 0).count();
    boolean hasNonFullBin = countNonEmptyBins > 0;
    if (!hasNonFullBin) {
      DTNSimGUI.cancelSim();
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
    List<Bin> availableBins = new ArrayList<>();
    for (var distanceBin: binHostPairs) {
      var binNeedsMoreMessages = distanceBin.count > 0;
      if (binNeedsMoreMessages) {
        availableBins.add(distanceBin);
      }
    }
    
    if (availableBins.isEmpty()) {
      return null;
    }
    
    // randomly pick from available bins
    Bin selectedBin = availableBins.get(rng.nextInt(availableBins.size()));
    
    // randomly pick an available pair from the bin and decrement the counter of more messages needed in the bin
    HostPair selectedPair = selectedBin.pairs.get(rng.nextInt(selectedBin.pairs.size()));
    selectedBin.count--;
    
    return selectedPair;
  }

    private List<Integer> calculateDistanceOptions(List<DTNHost> hosts) {
      return hosts.stream()
        .flatMap(h1 -> hosts.stream()
          .filter(h2 -> h1 != h2)
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
