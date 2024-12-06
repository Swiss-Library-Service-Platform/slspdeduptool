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
const brief_rec_fields = [
  'rec_id',
  'format',
  'title',
  'short_title',
  'creators',
  'corp_creators',
  'publishers',
  'date_1',
  'date_2',
  'editions',
  'extent',
  'language',
  'isbns',
  'issns',
  'other_std_num',
  'sysnums',
  'series',
  'parent'
];

/******************/
/* Vue Components */
/******************/

/* List of library records on the left with the filter */
const RecidList = {
  props: ['selectedLocRecid', 'recids'],
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
    <form class="mb-2" id="recordFilter">
    <label for="FilterOptions" class="control-label">Filter:</label>
      <select v-model="filterSelected" class="form-select form-select-sm" id="FilterOptions" @change="$emit('fetchRecList', filterSelected)">
        <option v-for="option in filterOptions" :value="option.value" :selected="option.value == filterSelected">{{ option.text }}</option>
      </select>
    </form>
    <div class="mb-2 mt-2">{{ recids.length }} records</div>
    <div id="recids" class="list-group">
      <a v-for="recid in recids" :class="{active: (recid.rec_id==selectedLocRecid), 'human-validated': recid.human_validated }" class="list-group-item list-group-item-action" href="#" @click="$emit('recordSelected', recid.rec_id)">{{ recid.rec_id }}</a>
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

/* Full NZ record or external record */
const FullExtNzRec = {
  props: ['fullExtNzRecData'],
  template: `
  <div id="extNzRecData" v-html="fullExtNzRecData">
  </div>`
}

/* Buttons on the right and list of possible matches */
const ActionSection = {
  props: ['possibleMatches', // list of records that could match with the library record
          'matchedRecord', // a record can already be defined as matched record.
          'selectedExtNzRecRank' // rank of the record actually displayed, default is matched record
  ],
  emits: ["extNzRecSelected", // click on a possible record
          "defineMatchingRecord", // click on the select matching record button
          "cancelMatchingRecord" // click on the cancel button
  ],
  template: `
    <div class="row m-2">
        <button id="dedup" class="btn btn-sm" :class="{'btn-primary': (selectedExtNzRecRank !== null)}" :disabled="selectedExtNzRecRank === null" @click="$emit('defineMatchingRecord', selectedExtNzRecRank)">Select matching record</button>
    </div>
    <div class="row m-2">
        <button id="local_dup" class="btn btn-sm btn-danger" @click="$emit('cancelMatchingRecord')">Cancel matching record</button>
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

/* Main Vue app */
const app = Vue.createApp({
  components: {RecidList, FullLocalRec, FullExtNzRec, ActionSection},
  data() {
    return {
      selectedLocRecid: null, // selected record ID of the library
      selectedLocRec: null, // selected record data of the library
      selectedExtNzRecRank: null,
      brief_rec_fields: brief_rec_fields,
      recids: []
    }
  },
  computed: {
    locBriefRec() {
      return this.selectedLocRec ? this.selectedLocRec.brief_rec : null;
    },
    locFullRec() {
      return this.selectedLocRec ? this.selectedLocRec.full_rec : null;
    },
    extNzBriefRec() {
      return this.selectedExtNzRecRank !== null ? this.selectedLocRec.possible_matches[this.selectedExtNzRecRank].brief_rec : null;
    },
    extNzFullRec() {
      return this.selectedExtNzRecRank !== null ? this.selectedLocRec.possible_matches[this.selectedExtNzRecRank].full_rec : null;
    },
    scores() {
      return this.selectedExtNzRecRank !== null ? this.selectedLocRec.possible_matches[this.selectedExtNzRecRank].scores : null;
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

      this.selectedLocRecid = recid; // set the selected record ID

      // Fetch the record data in backend
      fetch(`/dedup/locrec/${recid}`)
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
      fetch(`/dedup/locrec/${this.selectedLocRecid}`, {
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
      fetch(`/dedup/locrec/${this.selectedLocRecid}`, {
        method: 'POST',
        headers: {"X-CSRFToken": csrf_token}, // csrf_token is a global variable and required for POST requests
        body: JSON.stringify({'matched_record': ''})
      })
      .then(() => {
        this.makeHumanValidated(this.selectedLocRecid); // set human validated flag to true
        this.selectedLocRec.matched_record = ''; // reset the matched record
        this.fetchNextLocRec(this.selectedLocRecid); // fetch the next record and display it
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
        for (let field of this.brief_rec_fields) {
          if (field in possible_match['scores'] &&
              possible_match['scores'][field] !== null &&
              possible_match['scores'][field] !== 1) {
            possible_match['scores'][field] = possible_match['scores'][field].toFixed(2);
          }
        }
      });
    },

    /* Fetch the list of record IDs according to the provided filter */
    fetchRecList(filterSelected) {
      let recListUrl = '/dedup/locrecids';

      // Add filter to the URL if provided
      if (filterSelected) {
        recListUrl += `?filter=${filterSelected}`;
      }

      fetch(recListUrl)
      .then(response => response.json())
      .then(data => {
        this.recids = data['rec_ids'];
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
    }
  },
  template: `
    <header>
      <div class="row mb-2">
        <h1>SLSP dedup tool</h1>
      </div>
    </header>
    <div class="row">
      <aside class="col-1">
        <recidList :recids="recids" :selectedLocRecid="selectedLocRecid" @fetch-rec-list="fetchRecList" @record-selected="recordSelected">
        </recidList>
      </aside>
      <main class="col-9">
        <div class="row">
          <table class="table table-striped" id="brief_rec">
            <thead><tr>
                <th class="col-1"></th>
                <th class="col-5">Local brief record</th>
                <th class="col-5">NZ / external brief record</th>
                <th class="col-1">Score</th>
            </tr></thead>
            <tbody>
                <tr v-if="locBriefRec" v-for="field in brief_rec_fields" :class="{'table-danger': (extNzBriefRec && scores[field]!==null && scores[field]<0.8) }">
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
            <fullLocalRec :full-local-rec-data="locFullRec">
            </fullLocalRec>
          </div>
          <div class="col-6">
            <FullExtNzRec :full-ext-nz-rec-data="extNzFullRec">
            </FullExtNzRec>
          </div>
        </div>
      </main>
      <aside class="col-2">
        <ActionSection :possible-matches="possibleMatches" :selected-ext-nz-rec-rank="selectedExtNzRecRank" :matched-record="matchedRecord" @ext-nz-rec-selected="extNzRecSelected" @define-matching-record="defineMatchingRecord" @cancel-matching-record="cancelMatchingRecord"></ActionSection>
      </aside>
    </div>
  `
});

