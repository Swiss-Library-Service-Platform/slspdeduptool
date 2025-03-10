/********************************************/
/* Vue Components to manage the dedup tools */
/********************************************/

/*************/
/* Constants */
/*************/

/*
List of fields of local records
This list change according to the metadata
provided by the library.
*/
const full_local_rec_fields = [
  'rec_id',
  'title',
  'creators',
  'isbn',
  'publishers',
  'city',
  'year',
  'editions',
  'language',
  'extent',
  'parent',
  'content',
  'callnumber',
  'keywords',
  'review',
  'status',
  'format',
  'permalink',
  'category_2',
  'category_1'
];

/*
This list of field is common to local and
NZ + external. All brief records contains
same fields. Full records are already
transformed into brief records in the
database.
*/
const briefrec_fields = [
  'rec_id',
  'format',
  'titles',
  'short_titles',
  'creators',
  'corp_creators',
  'publishers',
  'years',
  'editions',
  'extent',
  'languages',
  'std_nums',
  'sys_nums',
  'series',
  'parent'
];

/******************/
/* Vue Components */
/******************/

/* List of library records on the left with the filter */
const RecidList = {
  props: ['selectedLocRecid', 'recids', 'nbTotalRecs'],
  data() {
    return {
      // Available options. The filter itself must be configured on the backend side
      filterOptions: [{value: 'all', text: 'All'},
                      {value: 'possible', text: 'Possible match'},
                      {value: 'match', text: 'match'},
                      {value: 'nomatch', text: 'No match'},
                      {value: 'duplicatematch', text: 'Duplicate match'}],

      // Default filter
      filterSelected: 'all',
      recidtofilter: ''
    }
  },
  methods: {
    handleIDFilterChange(event) {
      let recidfilter = event.target.value;
      if (recidfilter) {
        // console.log(recidfilter);
        this.recidfilter = recidfilter;
      }
    }
  },
  // Component emits event so that parent component fetch the list of record
  // IDs "fetchRecList".
  // If a user clicks on a specific record ID the component indicates it to the
  // parent "recordSelected".
  emits: ["fetchRecList", "recordSelected"],

  // "human_validated" is an attribute of recids that indicate if
  // a review
  template: `
    <h2 class="mb-0">Local IDs</h2>
    <form class="mb-2" id="recordFilter" @submit.prevent="$emit('fetchRecList', filterSelected, recidtofilter)">
      <label for="FilterOptions" class="control-label">Filter:</label>
      <select v-model="filterSelected" class="form-select form-select-sm" id="FilterOptions" @change="$emit('fetchRecList', filterSelected)">
        <option v-for="option in filterOptions" :value="option.value" :selected="option.value == filterSelected">{{ option.text }}</option>
      </select>
      <label for="IDFilter" class="control-label">Record ID:</label>
      <input id="IDFilter" type="text" class="form-control" v-model="recidtofilter" />

      <button id="nextRecords" class="btn btn-sm" type="button" @click="$emit('fetchRecList', filterSelected, null, true)">\u25B6</button>
      <button id="searchRecords" class="btn btn-sm" type="button" @click="$emit('fetchRecList', filterSelected, recidtofilter)">\u{1F50E}</button>

    </form>
    <div class="mb-2 mt-2">{{ nbTotalRecs }} records</div>
    <div id="recids" class="list-group">
      <a v-for="recid in recids" :class="{active: (recid.rec_id==selectedLocRecid), 'human-validated': recid.human_validated, 'list-group-item-dark': recid.color }" class="list-group-item list-group-item-action" href="#" @click="$emit('recordSelected', recid.rec_id)">{{ recid.rec_id }}</a>
    </div>
  `
};

/* Full record of the library */
const FullLocalRec = {
  props: ['fullLocalRecData'],
  data() {
    return {
      full_local_rec_fields: full_local_rec_fields
    }
  },
  // This component is only responsible for displaying content.
  template: `
  <table class="table" id="locFullRec">
    <tr v-if="fullLocalRecData" v-for="field in full_local_rec_fields">
      <th class="text-end">{{ field }}</th>
      <td>{{ fullLocalRecData[field] }}</td>
    </tr>
  </table>`
}

/* Full record */
const FullRec = {
  props: ['fullRecData'],
  template: `
  <div class="fullrecdata" v-html="fullRecData">
  </div>`
}

/* Buttons on the right and list of possible matches */
const ActionSection = {
  props: ['possibleMatches', // list of records that could match with the library record
          'matchedRecord', // a record can already be defined as matched record.
          'selectedExtNzRecRank', // rank of the record actually displayed, default is matched record
          'trainingDataMessage', // message to display after adding to training data
  ],
  emits: ["extNzRecSelected", // click on a possible record
          "defineMatchingRecord", // click on the select matching record button
          "cancelMatchingRecord", // click on the cancel button
          "addToTrainingData", // click on the training data button
  ],
  template: `
    <div class="row m-2">
        <button id="dedup" class="btn btn-sm" :class="{'btn-primary': (selectedExtNzRecRank !== null)}" :disabled="selectedExtNzRecRank === null" @click="$emit('defineMatchingRecord', selectedExtNzRecRank)">Select matching record</button>
    </div>
    <div class="row m-2">
        <button id="local_dup" class="btn btn-sm btn-danger" @click="$emit('cancelMatchingRecord')">Cancel matching record</button>
    </div>
    <div class="mt-4">
      <h2 class="row m-2">Add to training data</h2>
      <div class="row m-2 text-success" >{{ trainingDataMessage }}</div>
      <div class="row m-2">
          <button id="training_match" class="btn btn-sm" :class="{'btn-secondary': (selectedExtNzRecRank !== null)}" :disabled="selectedExtNzRecRank === null" @click="$emit('addToTrainingData', true)">Matching</button>
      </div>
      <div class="row m-2">
          <button id="training_nomatch" class="btn btn-sm" :class="{'btn-secondary': (selectedExtNzRecRank !== null)}" :disabled="selectedExtNzRecRank === null" @click="$emit('addToTrainingData', false)">Not matching</button>
      </div>
    </div>

    <div class="row m-2">
        <table class="table mt-4" id="matched_records">
            <thead><th class="col-10">Record ID</th><th class="col-2">score</th></thead>
            <tbody v-if="selectedExtNzRecRank === null">
              <tr><td colspan="2">No matched records found</td></tr>
            </tbody>
            <tbody v-else>
              <tr v-for="(possibleMatch, index) in possibleMatches" :class="{'table-primary': (index==selectedExtNzRecRank)}" >
                <th><a href="#" :class="{matchRecord: (possibleMatch.rec_id==matchedRecord)}" @click="$emit('extNzRecSelected', index)">{{ possibleMatch.rec_id }}</a></th>
                <td>{{ possibleMatch.similarity_score }}</td>
              </tr>
            </tbody>
        </table>
    </div>`
}

const SelectEvaluationModel = {
  data() {
    return {
      modelOptions: ['mean',
                     'random_forest_music'],
      modelSelected: 'mean' // default
  }},
  emits: ["defineEvaluationModel"],
  template: `<h2 class="mb-0">Evaluation models</h2>
    <form class="mb-2" id="selectModel">
      <label for="modelOptions" class="control-label">Current model:</label>
      <select v-model="modelSelected" class="form-select form-select-sm" id="modelOptions" @change="$emit('defineEvaluationModel', modelSelected)">
        <option v-for="option in modelOptions" :value="option" :selected="option == modelSelected">{{ option }}</option>
      </select>
    </form>`
}

/* Main Vue app */
const app = Vue.createApp({
  components: {RecidList, FullRec, ActionSection, SelectEvaluationModel},
  data() {
    return {
      selectedLocRecid: null, // selected record ID of the library
      selectedLocRec: null, // selected record data of the library
      selectedExtNzRecRank: null,
      briefrec_fields: briefrec_fields,
      recids: [],
      nbTotalRecs: null,
      trainingDataMessage: null,
      selectedModel: 'mean'
    }
  },
  computed: {
    locBriefRec() {
      return this.selectedLocRec ? this.selectedLocRec.briefrec : null;
    },
    locFullRec() {
      return this.selectedLocRec ? this.selectedLocRec.fullrec : null;
    },
    extNzBriefRec() {
      return (this.selectedExtNzRecRank !== null && this.selectedLocRec.possible_matches[this.selectedExtNzRecRank] !== undefined) ? this.selectedLocRec.possible_matches[this.selectedExtNzRecRank].briefrec : null;
    },
    extNzFullRec() {
      return (this.selectedExtNzRecRank !== null && this.selectedLocRec.possible_matches[this.selectedExtNzRecRank] !== undefined) ? this.selectedLocRec.possible_matches[this.selectedExtNzRecRank].fullrec : null;
    },
    scores() {
      return (this.selectedExtNzRecRank !== null  && this.selectedLocRec.possible_matches[this.selectedExtNzRecRank] !== undefined) ? this.selectedLocRec.possible_matches[this.selectedExtNzRecRank].scores : null;
    },
    possibleMatches() {
      return this.selectedLocRec ? this.selectedLocRec.possible_matches : null;
    },
    matchedRecord() {
      return this.selectedExtNzRecRank !== null && this.selectedLocRec.matched_record.length > 0 ? this.selectedLocRec.matched_record : null;
    }
  },
  created() {
    this.fetchRecList();
  },
  methods: {

    /* Fetch the selected record in the left list */
    recordSelected(recid) {
      this.trainingDataMessage = null;
      this.selectedLocRecid = recid; // set the selected record ID

      // Fetch the record data in backend
      fetch(`/dedup/col/${col_name}/locrec/${recid}?selectedModel=${this.selectedModel}`)
      .then(response => response.json())
      .then(data => {
        this.selectedLocRec = data;
        this.defineExtNzRecRank();
        if (this.selectedExtNzRecRank !== null) {this.truncateScores()}
      });
    },

    /* Select the external or NZ record */
    extNzRecSelected(index) {
      this.selectedExtNzRecRank = index; // this rank is used in computed properties to display the selected record
    },

    /* Define the rank of the external record */
    defineExtNzRecRank() {
      // matched record exists
      if (this.selectedLocRec && this.selectedLocRec.matched_record.length > 0) {
        this.selectedExtNzRecRank = this.selectedLocRec.possible_matches.findIndex(
          (possible_match) => possible_match.rec_id === this.selectedLocRec.matched_record
        );
      }
      // no matched record, but possible matches available
      else if (this.selectedLocRec.possible_matches.length > 0) {
          this.selectedExtNzRecRank = 0;
      }
      // No possible match available
      else {
        this.selectedExtNzRecRank = null;
      }
    },

    /* Manage the select matching record button */
    defineMatchingRecord(index) {
      fetch(`/dedup/col/${col_name}/locrec/${this.selectedLocRecid}`, {
        method: 'POST',
        headers: {"X-CSRFToken": csrf_token}, // csrf_token is a global variable and required for POST requests
        body: JSON.stringify({'matched_record': this.selectedLocRec.possible_matches[index].rec_id})
      })
      .then(response => response.json())
      .then(data => {
        this.makeHumanValidated(this.selectedLocRecid); // set human validated flag to true
        this.selectedLocRec.matched_record = this.selectedLocRec.possible_matches[index].rec_id; // set the matched record
        this.fetchNextLocRec(this.selectedLocRecid); // fetch the next record and display it
      });
    },

    /* Manage the cancel button */
    cancelMatchingRecord() {
      fetch(`/dedup/col/${col_name}/locrec/${this.selectedLocRecid}`, {
        method: 'POST',
        headers: {"X-CSRFToken": csrf_token}, // csrf_token is a global variable and required for POST requests
        body: JSON.stringify({'matched_record': null})
      })
      .then(() => {
        this.makeHumanValidated(this.selectedLocRecid); // set human validated flag to true
        this.selectedLocRec.matched_record = ''; // reset the matched record
        this.fetchNextLocRec(this.selectedLocRecid); // fetch the next record and display it
      });
    },

    /* Add to training data as matched record */
    addToTrainingData(ismatch) {
      fetch(`/dedup/training/add`, {
        method: 'POST',
        headers: {"X-CSRFToken": csrf_token}, // csrf_token is a global variable and required for POST requests
        body: JSON.stringify({'ext_nz_recid': this.selectedLocRec.possible_matches[this.selectedExtNzRecRank].rec_id,
                              'local_recid': this.selectedLocRecid,
                              'col_name': col_name,
                              'is_match': ismatch,
                              'selectedModel': this.selectedModel})
      })
      .then(response => response.json())
      .then(data => {
        this.trainingDataMessage = data['message'];
      });
    },

    /* Make human validated records */
    makeHumanValidated(recid) {
      this.recids.find(rec => rec.rec_id === recid).human_validated = true;
    },

    /* Truncate scores to 2 decimals */
    truncateScores() {
      this.selectedLocRec.possible_matches.forEach((possible_match) => {

        // Truncate global similarity score
        possible_match.similarity_score = possible_match.similarity_score.toFixed(2)

        // Truncate field similarity scores
        for (let field of this.briefrec_fields) {
          if (field in possible_match['scores'] &&
              possible_match['scores'][field] !== null &&
              possible_match['scores'][field] !== 1) {
            possible_match['scores'][field] = possible_match['scores'][field].toFixed(2);
          }
        }
      });
    },

    /* Fetch the list of record IDs according to the provided filter */
    fetchRecList(filterSelected=null, recid=null, next=false) {
      let recListUrl = `/dedup/col/${col_name}/locrecids`;

      // Add filter to the URL if provided
      if (filterSelected) {
        recListUrl += `?filter=${filterSelected}`;
      }

      if (recid) {
        recListUrl += recListUrl.includes('?') ? '&' : '?';
        recListUrl += `recid=${recid}`
      } else if (next && this.recids.length > 0) {
        recListUrl += recListUrl.includes('?') ? '&' : '?';
        let recid = this.recids.at(-1).rec_id;
        recListUrl += `next=${recid}`;
      }

      fetch(recListUrl)
      .then(response => response.json())
      .then(data => {
        this.recids = data['rec_ids'];
        this.nbTotalRecs = data['nb_total_recs'];
        // Select the first record in the list to display
        if (this.recids.length > 0) {this.recordSelected(this.recids[0]['rec_id']);}
      });
    },

    /* Fetch the next record in the list after clicking on one button (select or cancel) */
    fetchNextLocRec(recid) {
      let index = this.recids.findIndex(rec => rec.rec_id === recid);
      if (index < this.recids.length - 1) {
        this.recordSelected(this.recids[index + 1].rec_id);
      }
    },

    /* Define the evaluation model */
    defineEvaluationModel(model) {
      this.selectedModel = model;
      if (this.selectedLocRecid) {
        this.recordSelected(this.selectedLocRecid);
      }
    }
  },
  template: `
    <header>
      <div class="row">
        <div class="mb-2 col-10">
          <h1>SLSP dedup tool</h1>
        </div>
        <div class="mb-2 col-2 text-end">
          <a href="/dedup">Home</a>&nbsp;&nbsp;<a href="/dedup/logout">Logout</a>
        </div>
      </div>
    </header>
    <div class="row">
      <aside class="col-1">
        <recidList :recids="recids" :selectedLocRecid="selectedLocRecid" :nbTotalRecs="nbTotalRecs" @fetch-rec-list="fetchRecList" @record-selected="recordSelected" >
        </recidList>
      </aside>
      <main class="col-9">
        <div class="row">
          <table class="table table-striped" id="briefrec">
            <thead><tr>
                <th class="col-1"></th>
                <th class="col-5">Local brief record</th>
                <th class="col-5">NZ / external brief record</th>
                <th class="col-1">Score</th>
            </tr></thead>
            <tbody>
                <tr v-if="locBriefRec" v-for="field in briefrec_fields" :class="{'table-danger': (extNzBriefRec && scores[field]!==null && scores[field] >= 0.2 && scores[field] < 0.8) }">
                    <th class="text-end">{{ field }}</th>
                    <td>{{ locBriefRec[field] }}</td>
                    <td v-if="extNzBriefRec">{{ extNzBriefRec[field] }}</td>
                    <td v-else></td>
                    <td v-if="extNzBriefRec">{{ scores[field] }}</td>
                    <td v-else></td>
                </tr>
            </tbody>
          </table>
        </div>
        <div class="row">
          <div class="col-6">
            <FullRec :full-rec-data="locFullRec">
            </fullRec>
          </div>
          <div class="col-6">
            <FullRec :full-rec-data="extNzFullRec">
            </FullRec>
          </div>
        </div>
      </main>
      <aside class="col-2">
        <ActionSection :possible-matches="possibleMatches" :selected-ext-nz-rec-rank="selectedExtNzRecRank" :matched-record="matchedRecord" :training-data-message="trainingDataMessage" @ext-nz-rec-selected="extNzRecSelected" @define-matching-record="defineMatchingRecord" @cancel-matching-record="cancelMatchingRecord" @add-to-training-data="addToTrainingData"></ActionSection>
        <SelectEvaluationModel @defineEvaluationModel = "defineEvaluationModel"></SelectEvaluationModel>
      </aside>
    </div>`
});

